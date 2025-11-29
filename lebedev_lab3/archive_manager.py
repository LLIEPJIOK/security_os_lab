import json
import os
import platform
import tarfile
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Dict, List, Optional

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

if IS_WINDOWS:
    import pythonnet
    pythonnet.load("coreclr")
    
    import clr
    clr.AddReference(str(Path(r"acl/acl/bin/Release/net8.0/acl.dll").resolve()))
    
    from Acl import ACL as CSharpACL
    from Acl import AclHandler as CSharpAclHandler

if IS_LINUX:
    from linux_acl_handler import LinuxACL, LinuxAclHandler


class UniversalACL:
    def __init__(self):
        self.platform: str = platform.system()  # "Windows" или "Linux"
        self.data: Dict[str, Any] = {}
    
    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "data": self.data
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
    
    @staticmethod
    def from_dict(data: dict) -> "UniversalACL":
        acl = UniversalACL()
        acl.platform = data.get("platform", "Unknown")
        acl.data = data.get("data", {})
        return acl
    
    @staticmethod
    def from_json(json_str: str) -> "UniversalACL":
        data = json.loads(json_str)
        return UniversalACL.from_dict(data)
    
    @staticmethod
    def from_windows_acl(csharp_acl) -> "UniversalACL":
        acl = UniversalACL()
        acl.platform = "Windows"
        acl.data = json.loads(csharp_acl.ToJson())
        return acl
    
    @staticmethod
    def from_linux_acl(linux_acl: 'LinuxACL') -> "UniversalACL":
        acl = UniversalACL()
        acl.platform = "Linux"
        acl.data = linux_acl.to_dict()
        return acl
    
    def to_windows_acl(self):
        if not IS_WINDOWS:
            raise RuntimeError("Cannot create Windows ACL on non-Windows platform")
        json_str = json.dumps(self.data)
        return CSharpACL.FromJson(json_str)
    
    def to_linux_acl(self) -> 'LinuxACL':
        if not IS_LINUX:
            raise RuntimeError("Cannot create Linux ACL on non-Linux platform")
        return LinuxACL.from_dict(self.data)
    
    def merge(self, other: "UniversalACL"):
        if self.platform != other.platform:
            raise ValueError("Cannot merge ACLs from different platforms")
        
        if self.platform == "Windows":
            if not self.data.get("Owner"):
                self.data["Owner"] = other.data["Owner"]
            
            if not self.data.get("Group"):
                self.data["Group"] = other.data["Group"]
            
            # Merge Aces
            if "Aces" not in self.data:
                self.data["Aces"] = {}
            
            for sid, ace_list in other.data.get("Aces", {}).items():
                if sid not in self.data["Aces"]:
                    self.data["Aces"][sid] = []
                
                for ace in ace_list:
                    if ace in self.data["Aces"][sid]:
                        self.data["Aces"][sid].remove(ace)
                    self.data["Aces"][sid].append(ace)
            
            # Merge Saces
            if "Saces" not in self.data:
                self.data["Saces"] = {}
            
            for sid, ace_list in other.data.get("Saces", {}).items():
                if sid not in self.data["Saces"]:
                    self.data["Saces"][sid] = []
                
                for ace in ace_list:
                    if ace in self.data["Saces"][sid]:
                        self.data["Saces"][sid].remove(ace)
                    self.data["Saces"][sid].append(ace)
        
        elif self.platform == "Linux":
            if not self.data.get("owner"):
                self.data["owner"] = other.data["owner"]
            
            if not self.data.get("group"):
                self.data["group"] = other.data["group"]
            
            if not self.data.get("mode"):
                self.data["mode"] = other.data["mode"]
            
            # Merge acl_entries
            if "acl_entries" not in self.data:
                self.data["acl_entries"] = []
            
            for entry in other.data.get("acl_entries", []):
                if entry in self.data["acl_entries"]:
                    self.data["acl_entries"].remove(entry)
                self.data["acl_entries"].append(entry)


class PathAcl(Dict[str, UniversalACL]):
    def __init__(self):
        super().__init__()

    def __getitem__(self, key: str) -> UniversalACL:
        return super().__getitem__(key)

    def __setitem__(self, key: str, value: UniversalACL):
        if key in self:
            existing_acl = super().__getitem__(key)
            existing_acl.merge(value)
            super().__setitem__(key, existing_acl)
        else:
            super().__setitem__(key, value)


class SystemAclsDict(Dict[str, PathAcl]):
    def __init__(self):
        super().__init__()
        self.current_system = platform.system()

    def add_acl(self, system_name: str, file_path: str, acl: UniversalACL):
        if system_name not in self:
            super().__setitem__(system_name, PathAcl())
        
        self[system_name][file_path] = acl

    def get_acl(self, file_path: str) -> Optional[UniversalACL]:
        if self.current_system in self:
            return self[self.current_system].get(file_path)
        return None

    def get_current_system_acls(self) -> PathAcl:
        if self.current_system not in self:
            super().__setitem__(self.current_system, PathAcl())
        return self[self.current_system]

    def to_json(self) -> str:
        json_dict = {}
        for system_name, path_acls in super().items():
            json_dict[system_name] = {}
            for file_path, universal_acl in path_acls.items():
                json_dict[system_name][file_path] = universal_acl.to_dict()
        
        return json.dumps(json_dict, indent=4)
    
    @staticmethod
    def from_json(json_str: str) -> "SystemAclsDict":
        acls = SystemAclsDict()
        json_dict = json.loads(json_str)

        for system_name, files in json_dict.items():
            for file_path, acl_data in files.items():
                universal_acl = UniversalACL.from_dict(acl_data)
                acls.add_acl(system_name, file_path, universal_acl)

        return acls
    
    @staticmethod
    def load_from_source(p: Path) -> "SystemAclsDict":
        acls = SystemAclsDict()

        if (p.parent / ".acls").exists():
            with open(p.parent / ".acls", "r", encoding="utf-8") as f:
                json_str = f.read()

            inner = SystemAclsDict.from_json(json_str)
            for system_name, path_acls in super(SystemAclsDict, inner).items():
                for file_path, universal_acl in path_acls.items():
                    acls.add_acl(system_name, file_path, universal_acl)

        if p.is_file():
            return acls

        for acls_file in p.rglob(".acls"):
            rel_path = acls_file.relative_to(p.parent).parent
            
            with open(acls_file, "r", encoding="utf-8") as f:
                json_str = f.read()

            inner = SystemAclsDict.from_json(json_str)
            for system_name, path_acls in super(SystemAclsDict, inner).items():
                for file_path, universal_acl in path_acls.items():
                    full_path = (rel_path / file_path).as_posix()
                    acls.add_acl(system_name, full_path, universal_acl)

        return acls


class AclHandler:
    @staticmethod
    def GetFileAcl(file_path: str) -> UniversalACL:
        if IS_WINDOWS:
            csharp_acl = CSharpAclHandler.GetFileAcl(file_path)
            return UniversalACL.from_windows_acl(csharp_acl)
        elif IS_LINUX:
            linux_acl = LinuxAclHandler.get_file_acl(file_path)
            return UniversalACL.from_linux_acl(linux_acl)
        else:
            raise NotImplementedError(f"Platform {platform.system()} is not supported")
    
    @staticmethod
    def GetDirAcl(dir_path: str) -> UniversalACL:
        if IS_WINDOWS:
            csharp_acl = CSharpAclHandler.GetDirAcl(dir_path)
            return UniversalACL.from_windows_acl(csharp_acl)
        elif IS_LINUX:
            linux_acl = LinuxAclHandler.get_dir_acl(dir_path)
            return UniversalACL.from_linux_acl(linux_acl)
        else:
            raise NotImplementedError(f"Platform {platform.system()} is not supported")
    
    @staticmethod
    def SetFileAcl(file_path: str, universal_acl: UniversalACL):
        if IS_WINDOWS:
            csharp_acl = universal_acl.to_windows_acl()
            CSharpAclHandler.SetFileAcl(file_path, csharp_acl)
        elif IS_LINUX:
            linux_acl = universal_acl.to_linux_acl()
            LinuxAclHandler.set_file_acl(file_path, linux_acl)
        else:
            raise NotImplementedError(f"Platform {platform.system()} is not supported")
    
    @staticmethod
    def SetDirAcl(dir_path: str, universal_acl: UniversalACL):
        if IS_WINDOWS:
            csharp_acl = universal_acl.to_windows_acl()
            CSharpAclHandler.SetDirAcl(dir_path, csharp_acl)
        elif IS_LINUX:
            linux_acl = universal_acl.to_linux_acl()
            LinuxAclHandler.set_dir_acl(dir_path, linux_acl)
        else:
            raise NotImplementedError(f"Platform {platform.system()} is not supported")


def is_empty_dir(path: Path) -> bool:
    return path.is_dir() and not any(path.iterdir())


class ArchiveManager:
    @staticmethod
    def check_archive_exists(archive_path: str) -> bool:
        """Check if archive already exists."""
        return os.path.exists(archive_path)
    
    @staticmethod
    def get_conflicting_files(archive_path: str, destination_path: str) -> List[str]:
        """Get list of files that would be overwritten during unpacking."""
        conflicts = []
        output_dir = Path(destination_path)
        
        if not os.path.exists(archive_path):
            return conflicts
        
        try:
            with tarfile.open(archive_path, "r") as tar:
                for member in tar.getmembers():
                    if member.name == ".acls":
                        continue
                    full_path = output_dir / member.name
                    if full_path.exists():
                        conflicts.append(member.name)
        except Exception:
            pass
        
        return conflicts
    
    @staticmethod
    def pack(source_path: str, archive_path: str, progress_callback=None, force_overwrite: bool = False):
        source_path = Path(source_path)
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source path does not exist: {source_path}")
        
        if not force_overwrite and os.path.exists(archive_path):
            raise FileExistsError(f"Archive already exists: {archive_path}")
        
        parent = source_path.parent
        items = [p for p in [source_path] + list(source_path.rglob("*")) if p.name != ".acls"]
        total_items = len(items)
        
        acls = SystemAclsDict.load_from_source(source_path)

        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_acl_dir = Path(tmp_dir_name)

            with tarfile.open(archive_path, "w") as tar:
                for idx, item in enumerate(items, 1):
                    universal_acl = AclHandler.GetDirAcl(str(item)) if item.is_dir() else AclHandler.GetFileAcl(str(item))
                    
                    rel_path = item.relative_to(parent).as_posix()
                    acls.add_acl(acls.current_system, rel_path, universal_acl)

                    if item.is_file() or is_empty_dir(item):
                        tar.add(item, arcname=rel_path)

                    if progress_callback:
                        progress_callback(idx, total_items, f"Packing: {rel_path}")

                acl_json_str = acls.to_json()
                acl_json_path = tmp_acl_dir / ".acls"

                with open(acl_json_path, "w", encoding="utf-8") as f:
                    f.write(acl_json_str)

                tar.add(acl_json_path, arcname=".acls")

                if progress_callback:
                    progress_callback(total_items, total_items, "Packing completed!")
    
    @staticmethod
    def unpack(archive_path: str, destination_path: str, progress_callback=None, force_overwrite: bool = False):
        output_dir = Path(destination_path)
        
        if not force_overwrite:
            conflicts = ArchiveManager.get_conflicting_files(archive_path, destination_path)
            if conflicts:
                raise FileExistsError(f"Files would be overwritten: {', '.join(conflicts[:5])}{'...' if len(conflicts) > 5 else ''}")
        
        output_dir.mkdir(parents=True, exist_ok=True)

        existing_acls = SystemAclsDict()
        if (output_dir / ".acls").exists():
            try:
                with open(output_dir / ".acls", "r", encoding="utf-8") as f:
                    existing_json = f.read()
                existing_acls = SystemAclsDict.from_json(existing_json)
            except Exception:
                pass

        with tarfile.open(archive_path, "r") as tar:
            tar.extractall(path=output_dir)

        acl_file = output_dir / ".acls"
        with open(acl_file, "r", encoding="utf-8") as f:
            acl_json_str = f.read()

        archive_acls = SystemAclsDict.from_json(acl_json_str)
        
        for system_name, path_acls in super(SystemAclsDict, archive_acls).items():
            for file_path, universal_acl in path_acls.items():
                existing_acls.add_acl(system_name, file_path, universal_acl)
        
        merged_json = existing_acls.to_json()
        with open(acl_file, "w", encoding="utf-8") as f:
            f.write(merged_json)
        
        current_system_acls = archive_acls.get_current_system_acls()
        total_entries = len(current_system_acls)

        for idx, (file_path, universal_acl) in enumerate(current_system_acls.items(), 1):
            full_path = output_dir / file_path
            
            if full_path.is_file():
                AclHandler.SetFileAcl(str(full_path), universal_acl)
            elif full_path.is_dir():
                AclHandler.SetDirAcl(str(full_path), universal_acl)

            if progress_callback:
                progress_callback(idx, total_entries, f"Unpacking entry {idx}/{total_entries}")

        if progress_callback:
            progress_callback(total_entries, total_entries, "Unpacking completed!")
