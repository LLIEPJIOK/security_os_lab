using System.Security.AccessControl;
using System.Security.Principal;
using System.Text.Json;

namespace Acl;

public class Ace
{
    public string Identity { get; set; } = "";
    public string AccessType { get; set; } = "";
    public string Rights { get; set; } = "";
    public string InheritanceFlags { get; set; } = "";
    public string PropagationFlags { get; set; } = "";
}

public class ACL
{
    public List<Ace> Aces { get; set; } = new List<Ace>();
    private static readonly JsonSerializerOptions jsonOpts = new()
    {
        WriteIndented = true
    };

    public static ACL FromRules(AuthorizationRuleCollection rules)
    {
        var acl = new ACL();

        foreach (FileSystemAccessRule rule in rules)
        {
            acl.Aces.Add(new Ace
            {
                Identity = rule.IdentityReference.Value,
                AccessType = rule.AccessControlType.ToString(),
                Rights = rule.FileSystemRights.ToString(),
                InheritanceFlags = rule.InheritanceFlags.ToString(),
                PropagationFlags = rule.PropagationFlags.ToString()
            });
        }

        return acl;
    }

    public AuthorizationRuleCollection ToRules()
    {
        var rules = new AuthorizationRuleCollection();

        foreach (var ace in Aces)
        {
            var identity = new NTAccount(ace.Identity);
            var accessType = Enum.Parse<AccessControlType>(ace.AccessType);
            var rights = Enum.Parse<FileSystemRights>(ace.Rights);
            var inheritance = Enum.Parse<InheritanceFlags>(ace.InheritanceFlags);
            var propagation = Enum.Parse<PropagationFlags>(ace.PropagationFlags);

            var rule = new FileSystemAccessRule(
                identity,
                rights,
                inheritance,
                propagation,
                accessType
            );

            rules.AddRule(rule);
        }

        return rules;
    }

    public string ToJson()
    {
        return JsonSerializer.Serialize(this, jsonOpts);
    }

    public static ACL FromJson(string json)
    {
        return JsonSerializer.Deserialize<ACL>(json, jsonOpts) ?? new ACL();
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
            fileSecurity.AddAccessRule(newRule);
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
            dirSecurity.AddAccessRule(newRule);
        }

        dirInfo.SetAccessControl(dirSecurity);
    }
}