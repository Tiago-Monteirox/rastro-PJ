from __future__ import annotations

import base64
import re
import shutil
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

from ..contracts import SourceManifest, file_sha256, write_json_atomic

DEFAULT_SHARE_TOKEN = "YggdBLfdninEJX9"
DEFAULT_WEBDAV_ROOT = "https://arquivos.receitafederal.gov.br/public.php/dav/files"
SOURCE_FILE_PATTERN = re.compile(
    r"^(?:Empresas|Estabelecimentos|Socios)[0-9]+\.zip$|^(?:Simples|Municipios)\.zip$"
)


class ReceitaSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class RemoteSourceFile:
    competence: str
    source_type: str
    file_name: str
    url: str
    size_bytes: int
    etag: str | None = None
    last_modified: str | None = None


@dataclass(frozen=True)
class DownloadedSource:
    remote: RemoteSourceFile
    path: Path
    sha256: str

    def to_source_manifest(self) -> SourceManifest:
        return SourceManifest(
            source_type=self.remote.source_type,
            url=self.remote.url,
            file_name=self.remote.file_name,
            size_bytes=self.remote.size_bytes,
            sha256=self.sha256,
        )


def inventory_competence(
    competence: str,
    *,
    share_token: str = DEFAULT_SHARE_TOKEN,
    webdav_root: str = DEFAULT_WEBDAV_ROOT,
    opener: Callable = urllib.request.urlopen,
) -> tuple[RemoteSourceFile, ...]:
    _validate_competence(competence)
    directory_url = f"{webdav_root.rstrip('/')}/{share_token}/{competence}/"
    request = urllib.request.Request(
        directory_url,
        data=b'<?xml version="1.0"?><propfind xmlns="DAV:"><allprop/></propfind>',
        method="PROPFIND",
        headers={"Authorization": _authorization(share_token), "Depth": "1"},
    )
    try:
        with opener(request, timeout=60) as response:
            payload = response.read()
    except OSError as exc:
        raise ReceitaSourceError(f"Falha ao inventariar a competência {competence}.") from exc

    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ReceitaSourceError("Resposta WebDAV inválida.") from exc

    files = []
    namespace = {"d": "DAV:"}
    for response_node in root.findall("d:response", namespace):
        href = response_node.findtext("d:href", default="", namespaces=namespace)
        file_name = urllib.parse.unquote(href.rstrip("/").rsplit("/", 1)[-1])
        if not SOURCE_FILE_PATTERN.fullmatch(file_name):
            continue
        properties = response_node.find("d:propstat/d:prop", namespace)
        if properties is None:
            continue
        size_text = properties.findtext("d:getcontentlength", default="", namespaces=namespace)
        if not size_text.isdigit():
            raise ReceitaSourceError(f"Tamanho ausente para {file_name}.")
        files.append(
            RemoteSourceFile(
                competence=competence,
                source_type=_source_type(file_name),
                file_name=file_name,
                url=urllib.parse.urljoin(directory_url, urllib.parse.quote(file_name)),
                size_bytes=int(size_text),
                etag=_clean_etag(
                    properties.findtext("d:getetag", default="", namespaces=namespace)
                ),
                last_modified=properties.findtext(
                    "d:getlastmodified", default="", namespaces=namespace
                )
                or None,
            )
        )
    files.sort(key=lambda item: item.file_name)
    _validate_inventory(competence, files)
    return tuple(files)


def download_competence(
    competence: str,
    *,
    destination_root: Path,
    reserve_bytes: int = 20 * 1024**3,
    share_token: str = DEFAULT_SHARE_TOKEN,
    webdav_root: str = DEFAULT_WEBDAV_ROOT,
    opener: Callable = urllib.request.urlopen,
    workers: int = 4,
) -> tuple[DownloadedSource, ...]:
    inventory = inventory_competence(
        competence,
        share_token=share_token,
        webdav_root=webdav_root,
        opener=opener,
    )
    destination = Path(destination_root) / competence
    destination.mkdir(parents=True, exist_ok=True)
    _preflight_space(destination, inventory, reserve_bytes)

    if workers < 1 or workers > 8:
        raise ReceitaSourceError("Quantidade de workers deve estar entre 1 e 8.")

    def download_one(remote: RemoteSourceFile) -> DownloadedSource:
        path = destination / remote.file_name
        _download_resumable(
            remote,
            path,
            share_token=share_token,
            opener=opener,
        )
        return DownloadedSource(remote=remote, path=path, sha256=file_sha256(path))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        downloaded = list(executor.map(download_one, inventory))

    write_json_atomic(
        destination / "source-manifest.json",
        {
            "competence": competence,
            "share_url": f"{webdav_root.rstrip('/')}/{share_token}/{competence}/",
            "files": [
                {
                    **asdict(item.remote),
                    "path": item.path.name,
                    "sha256": item.sha256,
                }
                for item in downloaded
            ],
        },
    )
    return tuple(downloaded)


def _download_resumable(
    remote: RemoteSourceFile,
    destination: Path,
    *,
    share_token: str,
    opener: Callable,
) -> None:
    if destination.is_file() and destination.stat().st_size == remote.size_bytes:
        return
    partial = destination.with_name(f".{destination.name}.part")
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > remote.size_bytes:
        raise ReceitaSourceError(f"Parcial maior que a fonte: {remote.file_name}.")
    headers = {"Authorization": _authorization(share_token)}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(remote.url, headers=headers)
    try:
        with opener(request, timeout=120) as response:
            status = getattr(response, "status", response.getcode())
            append = offset > 0 and status == 206
            mode = "ab" if append else "wb"
            with partial.open(mode) as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
    except OSError as exc:
        raise ReceitaSourceError(f"Falha no download de {remote.file_name}.") from exc
    if partial.stat().st_size != remote.size_bytes:
        raise ReceitaSourceError(
            f"Tamanho de {remote.file_name} divergente: "
            f"{partial.stat().st_size} != {remote.size_bytes}."
        )
    partial.replace(destination)


def _preflight_space(
    destination: Path, inventory: tuple[RemoteSourceFile, ...], reserve_bytes: int
) -> None:
    remaining = 0
    for remote in inventory:
        complete = destination / remote.file_name
        partial = destination / f".{remote.file_name}.part"
        present = complete.stat().st_size if complete.exists() else 0
        if not present and partial.exists():
            present = partial.stat().st_size
        remaining += max(remote.size_bytes - present, 0)
    free = shutil.disk_usage(destination).free
    if free - remaining < reserve_bytes:
        raise ReceitaSourceError(
            f"Espaço insuficiente: livres={free}, download_restante={remaining}, "
            f"reserva={reserve_bytes}."
        )


def _validate_inventory(competence: str, files: list[RemoteSourceFile]) -> None:
    names = {item.file_name for item in files}
    for prefix in ("Empresas", "Estabelecimentos", "Socios"):
        shards = sorted(name for name in names if name.startswith(prefix))
        if len(shards) != 10:
            raise ReceitaSourceError(
                f"Inventário {competence} deveria conter 10 arquivos {prefix}; "
                f"encontrados={len(shards)}."
            )
    for required in ("Simples.zip", "Municipios.zip"):
        if required not in names:
            raise ReceitaSourceError(f"Inventário {competence} sem {required}.")
    if len(names) != len(files):
        raise ReceitaSourceError(f"Inventário {competence} contém nomes duplicados.")


def _authorization(share_token: str) -> str:
    credentials = base64.b64encode(f"{share_token}:".encode()).decode()
    return f"Basic {credentials}"


def _source_type(file_name: str) -> str:
    return re.sub(r"[0-9]+$", "", Path(file_name).stem).lower()


def _clean_etag(value: str) -> str | None:
    return value.strip('"') or None


def _validate_competence(value: str) -> None:
    if not re.fullmatch(r"20[0-9]{2}-(?:0[1-9]|1[0-2])", value):
        raise ReceitaSourceError(f"Competência inválida: {value}.")
