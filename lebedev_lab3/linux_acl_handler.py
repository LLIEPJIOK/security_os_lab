import grp
import json
import os
import pwd
import stat
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


class LinuxACL:
    def __init__(self):
        self.owner: Optional[int] = None
        self.group: Optional[int] = None
        self.mode: Optional[int] = None
        self.acl_entries: List[str] = []
    
    def to_dict(self) -> dict:
        return {
            "owner": self.owner,
            "group": self.group,
            "mode": oct(self.mode) if self.mode is not None else None,
            "acl_entries": self.acl_entries
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
    
    @staticmethod
    def from_dict(data: dict) -> "LinuxACL":
        acl = LinuxACL()
        acl.owner = data.get("owner")
        acl.group = data.get("group")

        mode_str = data.get("mode")
        acl.mode = int(mode_str, 8) if mode_str else None

        acl.acl_entries = data.get("acl_entries", [])

        return acl
    
    @staticmethod
    def from_json(json_str: str) -> "LinuxACL":
        data = json.loads(json_str)
        return LinuxACL.from_dict(data)
    
    def merge(self, other: "LinuxACL"):
        if other.owner is not None:
            self.owner = other.owner
        
        if other.group is not None:
            self.group = other.group
        
        if other.mode is not None:
            self.mode = other.mode
        
        for entry in other.acl_entries:
            if entry in self.acl_entries:
                self.acl_entries.remove(entry)
            self.acl_entries.append(entry)


class LinuxAclHandler:
    @staticmethod
    def get_file_acl(file_path: str) -> LinuxACL:
        acl = LinuxACL()
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        stat_info = path.stat()
        
        acl.owner = stat_info.st_uid
        acl.group = stat_info.st_gid

        acl.mode = stat.S_IMODE(stat_info.st_mode)
        
        try:
            result = subprocess.run(
                ['getfacl', '-p', file_path],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        acl.acl_entries.append(line)
        except FileNotFoundError:
            pass
        
        return acl
    
    @staticmethod
    def get_dir_acl(dir_path: str) -> LinuxACL:
        return LinuxAclHandler.get_file_acl(dir_path)
    
    @staticmethod
    def set_file_acl(file_path: str, acl: LinuxACL):
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if acl.owner is not None or acl.group is not None:
            try:
                uid = acl.owner if acl.owner is not None else path.stat().st_uid
                gid = acl.group if acl.group is not None else path.stat().st_gid
                
                os.chown(file_path, uid, gid)
            except (PermissionError, OSError) as e:
                print(f"Warning: Could not set owner/group: {e}")
        
        if acl.mode is not None:
            try:
                os.chmod(file_path, acl.mode)
            except PermissionError as e:
                print(f"Warning: Could not set permissions: {e}")
        
        if acl.acl_entries:
            try:
                # Сначала очищаем существующие ACL
                subprocess.run(
                    ['setfacl', '-b', file_path],
                    check=False,
                    capture_output=True
                )
                
                # Устанавливаем новые ACL
                for entry in acl.acl_entries:
                    subprocess.run(
                        ['setfacl', '-m', entry, file_path],
                        check=False,
                        capture_output=True
                    )
            except FileNotFoundError:
                print("Warning: setfacl not available, skipping extended ACL")
    
    @staticmethod
    def set_dir_acl(dir_path: str, acl: LinuxACL):
        LinuxAclHandler.set_file_acl(dir_path, acl)
    
    @staticmethod
    def format_mode(mode: int) -> str:
        perms = []
        
        # User permissions (rwx)
        perms.append('r' if mode & stat.S_IRUSR else '-')
        perms.append('w' if mode & stat.S_IWUSR else '-')
        # setuid: s если есть x, S если нет
        if mode & stat.S_ISUID:
            perms.append('s' if mode & stat.S_IXUSR else 'S')
        else:
            perms.append('x' if mode & stat.S_IXUSR else '-')
        
        # Group permissions (rwx)
        perms.append('r' if mode & stat.S_IRGRP else '-')
        perms.append('w' if mode & stat.S_IWGRP else '-')
        # setgid: s если есть x, S если нет
        if mode & stat.S_ISGID:
            perms.append('s' if mode & stat.S_IXGRP else 'S')
        else:
            perms.append('x' if mode & stat.S_IXGRP else '-')
        
        # Other permissions (rwx)
        perms.append('r' if mode & stat.S_IROTH else '-')
        perms.append('w' if mode & stat.S_IWOTH else '-')
        # sticky bit: t если есть x, T если нет
        if mode & stat.S_ISVTX:
            perms.append('t' if mode & stat.S_IXOTH else 'T')
        else:
            perms.append('x' if mode & stat.S_IXOTH else '-')
        
        return ''.join(perms)
    
    @staticmethod
    def parse_mode(mode_str: str) -> int:
        if mode_str.startswith('0') and len(mode_str) <= 5:
            return int(mode_str, 8)
        
        mode = 0
        
        if len(mode_str) < 9:
            raise ValueError(f"Invalid permission string: {mode_str}")
        
        # User permissions
        if mode_str[0] == 'r':
            mode |= stat.S_IRUSR
        if mode_str[1] == 'w':
            mode |= stat.S_IWUSR
        if mode_str[2] in ('x', 's'):
            mode |= stat.S_IXUSR
        if mode_str[2] in ('s', 'S'):
            mode |= stat.S_ISUID
        
        # Group permissions
        if mode_str[3] == 'r':
            mode |= stat.S_IRGRP
        if mode_str[4] == 'w':
            mode |= stat.S_IWGRP
        if mode_str[5] in ('x', 's'):
            mode |= stat.S_IXGRP
        if mode_str[5] in ('s', 'S'):
            mode |= stat.S_ISGID
        
        # Other permissions
        if mode_str[6] == 'r':
            mode |= stat.S_IROTH
        if mode_str[7] == 'w':
            mode |= stat.S_IWOTH
        if mode_str[8] in ('x', 't'):
            mode |= stat.S_IXOTH
        if mode_str[8] in ('t', 'T'):
            mode |= stat.S_ISVTX
        
        return mode
