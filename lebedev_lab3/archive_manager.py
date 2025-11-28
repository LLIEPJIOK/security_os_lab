import json
import os
import platform
import tarfile
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Dict, Union

# Определяем платформу
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

# Импортируем соответствующие модули в зависимости от платформы
if IS_WINDOWS:
    import pythonnet
    pythonnet.load("coreclr")
    
    import clr
    clr.AddReference(str(Path(r"acl/acl/bin/Release/net8.0/acl.dll").resolve()))
    
    from Acl import ACL as CSharpACL
    from Acl import AclHandler as CSharpAclHandler

if IS_LINUX:
    from linux_acl_handler import LinuxACL, LinuxAclHandler

# Универсальная обертка для работы с ACL
class AclHandler:
    @staticmethod
    def GetFileAcl(file_path: str):
        if IS_WINDOWS:
            return CSharpAclHandler.GetFileAcl(file_path)
        elif IS_LINUX:
            return LinuxAclHandler.get_file_acl(file_path)
        else:
            raise NotImplementedError(f"Platform {platform.system()} is not supported")
    
    @staticmethod
    def GetDirAcl(dir_path: str):
        if IS_WINDOWS:
            return CSharpAclHandler.GetDirAcl(dir_path)
        elif IS_LINUX:
            return LinuxAclHandler.get_dir_acl(dir_path)
        else:
            raise NotImplementedError(f"Platform {platform.system()} is not supported")
    
    @staticmethod
    def SetFileAcl(file_path: str, acl):
        if IS_WINDOWS:
            return CSharpAclHandler.SetFileAcl(file_path, acl)
        elif IS_LINUX:
            return LinuxAclHandler.set_file_acl(file_path, acl)
        else:
            raise NotImplementedError(f"Platform {platform.system()} is not supported")
    
    @staticmethod
    def SetDirAcl(dir_path: str, acl):
        if IS_WINDOWS:
            return CSharpAclHandler.SetDirAcl(dir_path, acl)
        elif IS_LINUX:
            return LinuxAclHandler.set_dir_acl(dir_path, acl)
        else:
            raise NotImplementedError(f"Platform {platform.system()} is not supported")


class PathAcl(Dict[str, Union['CSharpACL', 'LinuxACL']]):
    def __init__(self):
        super().__init__()

    def __getitem__(self, key: str):
        return super().__getitem__(key)

    def __setitem__(self, key: str, value):
        if key in self:
            acl = super().__getitem__(key)
            # Merge для C# ACL
            if IS_WINDOWS and hasattr(acl, 'Merge'):
                acl.Merge(value)
                super().__setitem__(key, acl)
            # Merge для Linux ACL
            elif IS_LINUX and hasattr(acl, 'merge'):
                acl.merge(value)
                super().__setitem__(key, acl)
            else:
                super().__setitem__(key, value)
        else:
            super().__setitem__(key, value)

    def __items__(self):
        for key in self:
            acl = self[key]
            if IS_WINDOWS and hasattr(acl, 'Aces'):
                yield key, [acl.Aces[ace_key] for ace_key in acl.Aces.Keys]
            else:
                yield key, acl


class SystemAclsDict(Dict[str, PathAcl]):
    def __init__(self):
        super().__init__()
        self.system = platform.system()
        super().__setitem__(self.system, PathAcl())

    def __getitem__(self, key: str):
        system_map = super().__getitem__(self.system)
        return system_map.get(key)

    def __setitem__(self, key: str, value):
        if self.system not in self:
            super().__setitem__(self.system, PathAcl())

        system_map = super().__getitem__(self.system)
        system_map[key] = value

    def __len__(self) -> int:
        if self.system not in self:
            return 0
        return len(super().__getitem__(self.system))

    def __iter__(self) -> Iterator[str]:
        if self.system not in self:
            return iter(())

        return iter(super().__getitem__(self.system))

    def keys(self):
        return super().__getitem__(self.system).keys()

    def items(self):
        return super().__getitem__(self.system).items()

    def values(self):
        return super().__getitem__(self.system).values()

    def to_json(self) -> str:
        json_dict = {}
        for system_name, files in super().items():
            json_dict[system_name] = {}
            for file_name, acl in files.items():
                # Для Windows используем C# метод ToJson
                if IS_WINDOWS and hasattr(acl, 'ToJson'):
                    json_dict[system_name][file_name] = acl.ToJson()
                # Для Linux используем Python метод to_json
                elif IS_LINUX and hasattr(acl, 'to_json'):
                    json_dict[system_name][file_name] = acl.to_json()
                else:
                    json_dict[system_name][file_name] = json.dumps(acl)

        return json.dumps(json_dict, indent=4)
    
    @staticmethod
    def from_json(json_str: str) -> "SystemAclsDict":
        acls = SystemAclsDict()
        json_dict = json.loads(json_str)

        for system_name, files in json_dict.items():
            super(SystemAclsDict, acls).__setitem__(system_name, PathAcl())
            for file_name, acl_json in files.items():
                # Определяем тип ACL по имени системы
                if system_name == "Windows" and IS_WINDOWS:
                    acl = CSharpACL.FromJson(acl_json)
                elif system_name == "Linux" and IS_LINUX:
                    from linux_acl_handler import LinuxACL
                    acl = LinuxACL.from_json(acl_json)
                else:
                    # Пропускаем ACL для других систем
                    continue
                
                super(SystemAclsDict, acls).__getitem__(system_name)[file_name] = acl

        return acls
    
    @staticmethod
    def load_from_dir(dir: Path) -> "SystemAclsDict":
        acls = SystemAclsDict()

        for acls_file in dir.rglob(".acls"):
            rel_path = acls_file.relative_to(dir).parent
            with open(acls_file, "r", encoding="utf-8") as f:
                json_str = f.read()

            inner = SystemAclsDict.from_json(json_str)
            for system_name, files in super(SystemAclsDict, inner).items():
                if system_name not in acls:
                    super(SystemAclsDict, acls).__setitem__(system_name, {})

                system_dict = super(SystemAclsDict, acls).__getitem__(system_name)
                for file_name, acl in files.items():
                    system_dict[str(rel_path / file_name)] = acl

        return acls


def is_empty_dir(path: Path) -> bool:
    return path.is_dir() and not any(path.iterdir())


class ArchiveManager:
    @staticmethod
    def pack(source_path: str, archive_path: str, progress_callback=None):
        source_path = Path(source_path)
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source path does not exist: {source_path}")
        
        parent = source_path.parent
        items = [p for p in [source_path] + list(source_path.rglob("*")) if p.name != ".acls"]
        total_items = len(items)
        
        acls = SystemAclsDict.load_from_dir(parent)

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_acl_dir = Path(tmp_dir_name)

            with tarfile.open(archive_path, "w") as tar:
                for idx, item in enumerate(items, 1):
                    acl = AclHandler.GetDirAcl(str(item)) if item.is_dir() else AclHandler.GetFileAcl(str(item))
                    acls[str(item.relative_to(parent))] = acl

                    if item.is_file() or is_empty_dir(item):
                        tar.add(item, arcname=item.relative_to(parent))

                    if progress_callback:
                        progress_callback(idx, total_items, f"Packing: {str(item.relative_to(source_path))}")

                acl_json_str = acls.to_json()
                acl_json_path = tmp_acl_dir / ".acls"

                with open(acl_json_path, "w", encoding="utf-8") as f:
                    f.write(acl_json_str)

                tar.add(acl_json_path, arcname=".acls")

                if progress_callback:
                    progress_callback(total_items, total_items, "Packing completed!")
    
    @staticmethod
    def unpack(archive_path: str, destination_path: str, progress_callback=None):
        output_dir = Path(destination_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(archive_path, "r") as tar:
            tar.extractall(path=output_dir)

        acl_file = output_dir / ".acls"
        with open(acl_file, "r", encoding="utf-8") as f:
            acl_json_str = f.read()

        acls = SystemAclsDict.from_json(acl_json_str)
        total_entries = len(acls)

        for idx, (file_path, acl) in enumerate(acls.items(), 1):
            file_path = output_dir / file_path
            if file_path.is_file():
                AclHandler.SetFileAcl(str(file_path), acl)
            elif file_path.is_dir():
                AclHandler.SetDirAcl(str(file_path), acl)

            if progress_callback:
                progress_callback(idx, total_entries, f"Unpacking entry {idx}/{total_entries}")

        if progress_callback:
            progress_callback(total_entries, total_entries, "Unpacking completed!")
