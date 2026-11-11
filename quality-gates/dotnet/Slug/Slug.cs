using System.Text;

namespace Samples;

public static class Slug
{
    public static string Make(string input)
    {
        ArgumentNullException.ThrowIfNull(input);
        var builder = new StringBuilder();
        var pendingHyphen = false;
        foreach (var c in input.ToLowerInvariant())
        {
            if (char.IsLetterOrDigit(c))
            {
                if (pendingHyphen && builder.Length > 0)
                {
                    builder.Append('-');
                }

                pendingHyphen = false;
                builder.Append(c);
                continue;
            }

            pendingHyphen = true;
        }

        return builder.ToString();
    }
}
