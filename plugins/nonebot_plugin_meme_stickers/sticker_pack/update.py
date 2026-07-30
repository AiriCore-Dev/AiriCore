import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from tempfile import TemporaryDirectory
from typing import Any, Callable, Optional
from typing_extensions import Unpack

from cookit.pyd import type_validate_json
from nonebot import logger

from ..consts import CONFIG_FILENAME, MANIFEST_FILENAME, UPDATING_FLAG_FILENAME
from ..utils import calc_checksum_from_file, dump_readable_model
from ..utils.file_source import (
    FileSource,
    ReqKwargs,
    fetch_source,
    with_kw_cli,
    with_kw_sem,
)
from .hub import fetch_manifest, fetch_optional_checksum
from .models import StickerPackConfig, StickerPackManifest


def validate_pack_file_path(path: str) -> str:
    if not path or "\x00" in path:
        raise ValueError(f"Invalid sticker pack file path: {path!r}")
    normalized = path.replace("\\", "/")
    posix_path = PurePosixPath(normalized)
    windows_path = PureWindowsPath(path)
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or ".." in posix_path.parts
    ):
        raise ValueError(f"Unsafe sticker pack file path: {path!r}")
    return path


def collect_manifest_files(manifest: StickerPackManifest) -> list[str]:
    files: list[str] = []
    if manifest.external_fonts:
        files.extend(x.path for x in manifest.external_fonts)
    if manifest.default_sticker_params.base_image:
        files.append(manifest.default_sticker_params.base_image)
    grid = manifest.sticker_grid
    files.extend(
        x
        for x in (
            grid.default_params.background,
            grid.category_override_params.background,
            *(x.background for x in grid.stickers_override_params.values()),
        )
        if isinstance(x, str)
    )
    files.extend(img for x in manifest.stickers if (img := x.params.base_image))
    return [validate_pack_file_path(path) for path in files]


def collect_local_files(path: Path) -> list[str]:
    ignored_paths = {
        (path / x)
        for x in {
            MANIFEST_FILENAME,
            CONFIG_FILENAME,
        }
    }
    return [
        x.relative_to(path).as_posix()
        for x in path.rglob("*")
        if x.is_file() and x not in ignored_paths
    ]


@dataclass
class UpdatedResourcesInfo:
    assets: set[str]
    fonts: set[str]


def _replace_path(src: Path, dst: Path) -> None:
    src.replace(dst)


def _restore_backup(backup_path: Path, pack_path: Path) -> None:
    try:
        _replace_path(backup_path, pack_path)
    except Exception:
        if pack_path.exists():
            shutil.rmtree(pack_path)
        shutil.copytree(backup_path, pack_path, symlinks=True)
        shutil.rmtree(backup_path)


def _commit_staging(staging_path: Path, pack_path: Path) -> None:
    if not pack_path.exists():
        _replace_path(staging_path, pack_path)
        return

    backup_path = staging_path.with_name(f"{staging_path.name}-backup")
    _replace_path(pack_path, backup_path)
    try:
        _replace_path(staging_path, pack_path)
    except Exception:
        _restore_backup(backup_path, pack_path)
        raise

    try:
        shutil.rmtree(backup_path)
    except Exception as e:
        logger.warning(f"贴纸包 `{pack_path.name}` 旧目录清理失败: {e}")


async def update_sticker_pack(
    pack_path: Path,
    source: FileSource,
    manifest: Optional[StickerPackManifest] = None,
    file_update_start_callback: Optional[Callable[[], Any]] = None,
    **req_kw: Unpack[ReqKwargs],
):
    slug = pack_path.name

    if (pack_path / UPDATING_FLAG_FILENAME).exists():
        raise RuntimeError(f"Pack `{slug}` is updating")

    if manifest is None:
        logger.debug(f"Fetching manifest of pack `{slug}`")
        manifest = await fetch_manifest(source, **req_kw)

    logger.debug(f"Fetching resource file checksums of pack `{slug}`")
    checksum = await fetch_optional_checksum(source, **req_kw)

    logger.debug(f"Collecting files need to update for pack `{slug}`")

    local_files = (
        set(collect_local_files(pack_path)) if pack_path.exists() else set[str]()
    )
    remote_files = set(collect_manifest_files(manifest))

    files_should_download = remote_files - local_files

    exist_files_not_in_pack_dir = {
        x for x in files_should_download if (pack_path / x).exists()
    }
    files_should_download -= exist_files_not_in_pack_dir

    file_both_exist = (
        {*local_files, *exist_files_not_in_pack_dir} & remote_files
    )
    if checksum:
        both_exist_checksum = {
            x: calc_checksum_from_file(pack_path / x) for x in file_both_exist
        }
        files_should_download.update(
            x for x, c in both_exist_checksum.items() if checksum.get(x) != c
        )
    else:
        files_should_download.update(file_both_exist)

    download_total = len(files_should_download)
    downloaded_count = 0

    async def download(staging_path: Path, path: str):
        nonlocal downloaded_count
        r = await fetch_source(source, path, **req_kw)
        p = staging_path / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(r.content)
        downloaded_count += 1
        is_info = downloaded_count % 10 == 0 or (
            downloaded_count in (1, download_total)
        )
        logger.log(
            "INFO" if is_info else "DEBUG",
            (
                f"[{downloaded_count} / {download_total}] "
                f"Downloaded of pack `{slug}`: {path}"
            ),
        )

    def after_ops(staging_path: Path):
        files_should_remove = local_files - remote_files
        if files_should_remove:
            logger.info(
                f"Removing {len(files_should_remove)} not needed files from pack `{slug}`",
            )
            for path in files_should_remove:
                (staging_path / path).unlink()

        empty_folders = tuple(
            p
            for p in staging_path.rglob("*")
            if p.is_dir() and not any(p.iterdir())
        )
        if empty_folders:
            logger.info(
                f"Removing {len(empty_folders)} empty folders from pack `{slug}`",
            )
            for p in empty_folders:
                p.rmdir()

        logger.debug(f"Updating manifest and config of pack `{slug}`")
        (staging_path / MANIFEST_FILENAME).write_text(
            dump_readable_model(manifest, exclude_defaults=True, exclude_unset=True),
            "u8",
        )

        config_path = staging_path / CONFIG_FILENAME
        config = (
            type_validate_json(StickerPackConfig, config_path.read_text("u8"))
            if config_path.exists()
            else StickerPackConfig()
        )
        config.update_source = source
        config_path.write_text(
            dump_readable_model(config, exclude_unset=True),
            "u8",
        )

    pack_path.parent.mkdir(parents=True, exist_ok=True)
    pack_created_for_flag = not pack_path.exists()
    pack_path.mkdir(exist_ok=True)
    flag_path = pack_path / UPDATING_FLAG_FILENAME
    try:
        flag_path.touch(exist_ok=False)
    except FileExistsError:
        raise RuntimeError(f"Pack `{slug}` is updating")
    try:
        with TemporaryDirectory(
            dir=pack_path.parent,
            prefix=f".{slug}-staging-",
        ) as staging_dir:
            staging_path = Path(staging_dir)
            shutil.copytree(
                pack_path,
                staging_path,
                dirs_exist_ok=True,
                symlinks=True,
            )
            (staging_path / UPDATING_FLAG_FILENAME).unlink(missing_ok=True)

            if download_total:
                logger.info(
                    f"Pack `{slug}`"
                    f" collected {download_total} files will update from remote,"
                    f" downloading to temp dir",
                )
                async with with_kw_cli(req_kw), with_kw_sem(req_kw):
                    await asyncio.gather(
                        *(download(staging_path, x) for x in files_should_download),
                    )
            else:
                logger.info(f"No files need to update for pack `{slug}`")

            after_ops(staging_path)
            if file_update_start_callback:
                file_update_start_callback()
            _commit_staging(staging_path, pack_path)
    finally:
        flag_path.unlink(missing_ok=True)
        if pack_created_for_flag and pack_path.exists() and not any(pack_path.iterdir()):
            pack_path.rmdir()

    external_fonts_updated = {
        x.path for x in manifest.external_fonts if x.path in files_should_download
    }
    if external_fonts_updated:
        logger.warning(f"Base path: {pack_path}")
        logger.warning(f"Pack `{slug}` updated with the following external font(s).")
        logger.warning(f"贴纸包 `{slug}` 更新了如下额外字体文件，")
        logger.warning(
            "Don't forget to install them into system then restart bot to use!",
        )
        logger.warning(
            "请不要忘记安装这些字体文件到系统中，然后重启 Bot 以正常使用本插件功能！",
        )
        for x in external_fonts_updated:
            logger.warning(f"  - {x}")

    logger.info(f"Successfully updated pack `{slug}`")
    return UpdatedResourcesInfo(
        assets=files_should_download - external_fonts_updated,
        fonts=external_fonts_updated,
    )
