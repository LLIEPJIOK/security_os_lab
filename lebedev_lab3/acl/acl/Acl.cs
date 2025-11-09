using System.Security.AccessControl;
using System.Security.Principal;
using System.Text.Json;

namespace Acl;

public class Ace
{
    public string Identity { get; set; } = "";
    public string AccessType { get; set; } = "";
    public int Rights { get; set; }
    public string InheritanceFlags { get; set; } = "";
    public string PropagationFlags { get; set; } = "";
}

public class ACL
{
    public Dictionary<string, List<Ace>> Aces { get; set; } = [];
    private static readonly JsonSerializerOptions jsonOpts = new()
    {
        WriteIndented = true
    };

    public static ACL FromRules(AuthorizationRuleCollection rules)
    {
        var acl = new ACL();
        foreach (FileSystemAccessRule rule in rules)
        {
            if (!acl.Aces.ContainsKey(rule.IdentityReference.Value))
            {
                acl.Aces[rule.IdentityReference.Value] = [];
            }

            acl.Aces[rule.IdentityReference.Value].Add(new Ace
            {
                Identity = rule.IdentityReference.Value,
                AccessType = rule.AccessControlType.ToString(),
                Rights = (int)rule.FileSystemRights,
                InheritanceFlags = rule.InheritanceFlags.ToString(),
                PropagationFlags = rule.PropagationFlags.ToString()
            });
        }

        return acl;
    }

    public AuthorizationRuleCollection ToRules()
    {
        var rules = new AuthorizationRuleCollection();

        foreach (var (_, aceList) in Aces)
        {
            foreach (var ace in aceList)
            {
                var identity = new NTAccount(ace.Identity);
                var accessType = Enum.Parse<AccessControlType>(ace.AccessType);
                var inheritance = Enum.Parse<InheritanceFlags>(ace.InheritanceFlags);
                var propagation = Enum.Parse<PropagationFlags>(ace.PropagationFlags);
                var rights = (FileSystemRights)ace.Rights;

                var rule = new FileSystemAccessRule(identity, rights, inheritance, propagation, accessType);
                rules.AddRule(rule);
            }
        }

        return rules;
    }

    public string ToJson()
    {
        return JsonSerializer.Serialize(Aces, jsonOpts);
    }


    public static ACL FromJson(string json)
    {
        var acl = new ACL();

        var d = JsonSerializer.Deserialize<Dictionary<string, List<Ace>>>(json, jsonOpts);
        acl.Aces = d ?? [];

        return acl;
    }
}

public class AclHandler
{
    public static ACL GetFileAcl(string filePath)
    {
        var fileInfo = new FileInfo(filePath);
        var fileSecurity = fileInfo.GetAccessControl();
        AuthorizationRuleCollection rules = fileSecurity.GetAccessRules(true, true, typeof(NTAccount));

        return ACL.FromRules(rules);
    }

    public static void SetFileAcl(string filePath, ACL acl)
    {
        var fileInfo = new FileInfo(filePath);
        FileSecurity fileSecurity = fileInfo.GetAccessControl();
        AuthorizationRuleCollection newRules = acl.ToRules();

        AuthorizationRuleCollection existingRules = fileSecurity.GetAccessRules(true, false, typeof(NTAccount));
        foreach (FileSystemAccessRule existingRule in existingRules)
        {
            fileSecurity.RemoveAccessRule(existingRule);
        }

        foreach (FileSystemAccessRule newRule in newRules)
        {
            try
            {
                fileSecurity.AddAccessRule(newRule);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Warning: Cannot apply rule for {newRule.IdentityReference}: {ex.Message}");
            }
        }

        fileInfo.SetAccessControl(fileSecurity);
    }

    public static ACL GetDirAcl(string directoryPath)
    {
        var dirInfo = new DirectoryInfo(directoryPath);
        var dirSecurity = dirInfo.GetAccessControl();
        AuthorizationRuleCollection rules = dirSecurity.GetAccessRules(true, true, typeof(NTAccount));

        return ACL.FromRules(rules);
    }

    public static void SetDirAcl(string directoryPath, ACL acl)
    {
        var dirInfo = new DirectoryInfo(directoryPath);
        DirectorySecurity dirSecurity = dirInfo.GetAccessControl();
        AuthorizationRuleCollection newRules = acl.ToRules();

        AuthorizationRuleCollection existingRules = dirSecurity.GetAccessRules(true, false, typeof(NTAccount));
        foreach (FileSystemAccessRule existingRule in existingRules)
        {
            dirSecurity.RemoveAccessRule(existingRule);
        }

        foreach (FileSystemAccessRule newRule in newRules)
        {
            try
            {
                dirSecurity.AddAccessRule(newRule);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Warning: Cannot apply rule for {newRule.IdentityReference}: {ex.Message}");
            }
        }

        dirInfo.SetAccessControl(dirSecurity);
    }
}