using CsCheck;
using Samples;

namespace Samples.Tests;

public class SlugProperties
{
    [Fact]
    public void MakeIsIdempotentAndHasNoStrayHyphens() =>
        Gen.String.Sample(input =>
        {
            var slug = Slug.Make(input);
            return Slug.Make(slug) == slug
                && !slug.StartsWith('-')
                && !slug.EndsWith('-')
                && !slug.Contains("--", StringComparison.Ordinal);
        });
}
