using System.Security.AccessControl;
using System.Security.Principal;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Acl;

public class ACL
{
    public string? Owner { get; set; }
    public string? Group { get; set; }
    public Dictionary<string, List<string>> Aces { get; set; } = [];
    public Dictionary<string, List<string>> Saces { get; set; } = [];
    private static readonly JsonSerializerOptions jsonOpts = new()
    {
        WriteIndented = true
    };

    public static ACL FromSddl(string sddl)
    {
        var acl = new ACL();

        // Parse Owner (O:) - match until next section or end
        var ownerMatch = Regex.Match(sddl, @"O:(.*?)(?=G:|D:|S:|$)", RegexOptions.Singleline);
        if (ownerMatch.Success && ownerMatch.Groups[1].Value.Length > 0)
        {
            acl.Owner = ownerMatch.Groups[1].Value.Trim();
        }

        // Parse Group (G:) - match until next section or end
        var groupMatch = Regex.Match(sddl, @"G:(.*?)(?=D:|S:|$)", RegexOptions.Singleline);
        if (groupMatch.Success && groupMatch.Groups[1].Value.Length > 0)
        {
            acl.Group = groupMatch.Groups[1].Value.Trim();
        }

        // Parse DACL (D:) - match until S: or end
        var daclMatch = Regex.Match(sddl, @"D:(.*?)(?=S:|$)", RegexOptions.Singleline);
        if (daclMatch.Success && daclMatch.Groups[1].Value.Length > 0)
        {
            var daclPart = daclMatch.Groups[1].Value;
            ParseAces(daclPart, acl.Aces);
        }

        // Parse SACL (S:) - match until end
        var saclMatch = Regex.Match(sddl, @"S:(.*)$", RegexOptions.Singleline);
        if (saclMatch.Success && saclMatch.Groups[1].Value.Length > 0)
        {
            var saclPart = saclMatch.Groups[1].Value;
            ParseAces(saclPart, acl.Saces);
        }

        return acl;
    }

    private static void ParseAces(string aclPart, Dictionary<string, List<string>> aceDict)
    {
        // Parse ACEs - each ACE is in format (ace_type;ace_flags;rights;object_guid;inherit_object_guid;account_sid)
        var acePattern = @"\(([^)]+)\)";
        var aceMatches = Regex.Matches(aclPart, acePattern);

        foreach (Match aceMatch in aceMatches)
        {
            var aceString = aceMatch.Groups[1].Value;
            var parts = aceString.Split(';');

            // SDDL ACE format: (type;flags;rights;object_guid;inherit_object_guid;sid)
            if (parts.Length >= 6)
            {
                var sid = parts[5];
                var fullAce = aceMatch.Value; // Includes parentheses

                if (!aceDict.ContainsKey(sid))
                {
                    aceDict[sid] = [];
                }

                aceDict[sid].Add(fullAce);
            }
        }
    }

    private static bool IsValidSid(string sid)
    {
        if (string.IsNullOrEmpty(sid))
            return false;

        try
        {
            var securityIdentifier = new SecurityIdentifier(sid);
            securityIdentifier.Translate(typeof(NTAccount));
            return true;
        }
        catch
        {
            return false;
        }
    }

    private static string? ExtractSidFromAce(string ace)
    {
        // Extract SID from ACE format: (type;flags;rights;object_guid;inherit_object_guid;sid)
        var aceContent = ace.Trim('(', ')');
        var parts = aceContent.Split(';');
        return parts.Length >= 6 ? parts[5] : null;
    }

    public string ToSddl()
    {
        var sddl = "";

        if (!string.IsNullOrEmpty(Owner))
        {
            if (Owner.StartsWith("S-") && !IsValidSid(Owner))
            {
                Console.WriteLine($"Warning: Skipping invalid owner SID: {Owner}");
            }
            else
            {
                sddl += $"O:{Owner}";
            }
        }

        if (!string.IsNullOrEmpty(Group))
        {
            if (Group.StartsWith("S-") && !IsValidSid(Group))
            {
                Console.WriteLine($"Warning: Skipping invalid group SID: {Group}");
            }
            else
            {
                sddl += $"G:{Group}";
            }
        }

        var allAces = Aces.Values.SelectMany(x => x)
            .Where(ace =>
            {
                var sid = ExtractSidFromAce(ace);
                if (sid != null && sid.StartsWith("S-") && !IsValidSid(sid))
                {
                    Console.WriteLine($"Warning: Skipping ACE with invalid SID: {sid}");
                    return false;
                }
                return true;
            })
            .ToList();

        var sortedAces = allAces
            .Select(ace => new
            {
                Raw = ace,
                Type = ace.Split(';')[0].Trim('(')
            })
            .OrderBy(ace => ace.Type switch
            {
                "D" => 1,
                "OD" => 2,
                "A" => 3,
                "OA" => 4,
                _ => 5 // inherited or unknown
            })
            .Select(ace => ace.Raw)
            .ToList();

        sddl += "D:";
        foreach (var ace in sortedAces)
        {
            sddl += ace;
        }

        if (Saces.Count > 0)
        {
            var validSaces = new List<string>();
            foreach (var (sid, aceList) in Saces)
            {
                foreach (var ace in aceList)
                {
                    var aceSid = ExtractSidFromAce(ace);
                    if (aceSid != null && aceSid.StartsWith("S-") && !IsValidSid(aceSid))
                    {
                        Console.WriteLine($"Warning: Skipping SACE with invalid SID: {aceSid}");
                        continue;
                    }
                    validSaces.Add(ace);
                }
            }

            if (validSaces.Count > 0)
            {
                sddl += "S:";
                foreach (var ace in validSaces)
                {
                    sddl += ace;
                }
            }
        }

        return sddl;
    }

    public string ToJson()
    {
        var data = new
        {
            Owner,
            Group,
            Aces,
            Saces
        };
        return JsonSerializer.Serialize(data, jsonOpts);
    }

    public static ACL FromJson(string json)
    {
        var acl = new ACL();
        using (JsonDocument doc = JsonDocument.Parse(json))
        {
            var root = doc.RootElement;

            if (root.TryGetProperty("Owner", out var ownerProp))
                acl.Owner = ownerProp.GetString();

            if (root.TryGetProperty("Group", out var groupProp))
                acl.Group = groupProp.GetString();

            if (root.TryGetProperty("Aces", out var acesProp))
                acl.Aces = JsonSerializer.Deserialize<Dictionary<string, List<string>>>(acesProp.GetRawText(), jsonOpts) ?? [];

            if (root.TryGetProperty("Saces", out var sacesProp))
                acl.Saces = JsonSerializer.Deserialize<Dictionary<string, List<string>>>(sacesProp.GetRawText(), jsonOpts) ?? [];
        }
        return acl;
    }

    public void Merge(ACL other)
    {
        // Merge Owner
        if (!string.IsNullOrEmpty(other.Owner))
        {
            Owner = other.Owner;
        }

        // Merge Group
        if (!string.IsNullOrEmpty(other.Group))
        {
            Group = other.Group;
        }

        // Merge Aces (DACL)
        foreach (var (sid, aceList) in other.Aces)
        {
            if (!Aces.ContainsKey(sid))
            {
                Aces[sid] = [];
            }

            foreach (var ace in aceList)
            {
                Aces[sid].Remove(ace);
                Aces[sid].Add(ace);
            }
        }

        // Merge Saces (SACL)
        foreach (var (sid, aceList) in other.Saces)
        {
            if (!Saces.ContainsKey(sid))
            {
                Saces[sid] = [];
            }

            foreach (var ace in aceList)
            {
                Saces[sid].Remove(ace);
                Saces[sid].Add(ace);
            }
        }
    }
}

public class AclHandler
{
    public static ACL GetFileAcl(string filePath)
    {
        var fileInfo = new FileInfo(filePath);
        var fileSecurity = fileInfo.GetAccessControl();
        string sddl = fileSecurity.GetSecurityDescriptorSddlForm(AccessControlSections.All);

        return ACL.FromSddl(sddl);
    }

    public static void SetFileAcl(string filePath, ACL acl)
    {
        var fileInfo = new FileInfo(filePath);
        var fileSecurity = fileInfo.GetAccessControl();
        string newSddl = acl.ToSddl();

        try
        {
            fileSecurity.SetSecurityDescriptorSddlForm(newSddl);
            fileInfo.SetAccessControl(fileSecurity);
        }
        catch
        {
            Console.WriteLine("Failed to set ACL for file: " + filePath);
        }
    }

    public static ACL GetDirAcl(string directoryPath)
    {
        var dirInfo = new DirectoryInfo(directoryPath);
        var dirSecurity = dirInfo.GetAccessControl();
        string sddl = dirSecurity.GetSecurityDescriptorSddlForm(AccessControlSections.All);

        return ACL.FromSddl(sddl);
    }

    public static void SetDirAcl(string directoryPath, ACL acl)
    {
        var dirInfo = new DirectoryInfo(directoryPath);
        var dirSecurity = dirInfo.GetAccessControl();
        string newSddl = acl.ToSddl();

        try
        {
            dirSecurity.SetSecurityDescriptorSddlForm(newSddl);
            dirInfo.SetAccessControl(dirSecurity);
        }
        catch
        {
            Console.WriteLine("Failed to set ACL for directory: " + directoryPath);
        }
    }
}