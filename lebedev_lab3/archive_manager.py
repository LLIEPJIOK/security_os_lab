import os
from pathlib import Path
import tarfile
import tempfile

import pythonnet
pythonnet.load("coreclr")

import clr
clr.AddReference(str(Path(r"acl/acl/bin/Release/net8.0/acl.dll").resolve()))

from Acl import AclHandler, ACL

class ArchiveManager:
    @staticmethod
    def pack(source_path: str, archive_path: str, progress_callback=None):
        source_path = Path(source_path).resolve()
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source path does not exist: {source_path}")
        
        items = [source_path] + list(source_path.rglob("*"))
        total_items = len(items)

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_acl_dir = Path(tmp_dir_name)

            with tarfile.open(archive_path, "w") as tar:
                for idx, item in enumerate(items, 1):
                    acl = AclHandler.GetDirAcl(str(item)) if item.is_dir() else AclHandler.GetFileAcl(str(item))
                    acl_json = acl.ToJson()

                    acl_json_path = tmp_acl_dir / item.relative_to(source_path.parent)
                    acl_json_path = acl_json_path.with_suffix(acl_json_path.suffix + ".acl.json")
                    acl_json_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(acl_json_path, "w", encoding="utf-8") as f:
                        f.write(acl_json)

                    if item.is_file():
                        tar.add(item, arcname=item.relative_to(source_path.parent))
                    tar.add(acl_json_path, arcname=acl_json_path.relative_to(tmp_acl_dir))

                    if progress_callback:
                        progress_callback(idx, total_items, f"Packing: {str(item.relative_to(source_path))}")
                
                if progress_callback:
                    progress_callback(total_items, total_items, "Packing completed!")
    
    @staticmethod
    def unpack(archive_path: str, destination_path: str, progress_callback=None):
        output_dir = Path(destination_path).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(archive_path, "r") as tar:
            tar.extractall(path=output_dir)

        acl_files = list(output_dir.rglob("*.acl.json"))
        acl_files.sort(key=lambda p: len(str(p)), reverse=True)
        total_entries = len(acl_files)

        for idx, acl_file in enumerate(acl_files, 1):
            data_file = Path(str(acl_file).replace(".acl.json", ""))
            with open(acl_file, "r", encoding="utf-8") as f:
                acl_data = f.read()

            acl = ACL.FromJson(acl_data)

            if data_file.is_file():
                AclHandler.SetFileAcl(str(data_file), acl)
            elif data_file.is_dir():
                AclHandler.SetDirAcl(str(data_file), acl)

            acl_file.unlink()

            if progress_callback:
                progress_callback(idx, total_entries, f"Unpacking entry {idx}/{total_entries}")
        
        if progress_callback:
            progress_callback(total_entries, total_entries, "Unpacking completed!")
