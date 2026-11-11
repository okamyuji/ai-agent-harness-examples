package slug

import (
	"strings"
	"testing"

	"pgregory.net/rapid"
)

func TestMakeProperties(t *testing.T) {
	rapid.Check(t, func(t *rapid.T) {
		in := rapid.String().Draw(t, "in")
		out := Make(in)
		if Make(out) != out {
			t.Fatalf("not idempotent: %q -> %q -> %q", in, out, Make(out))
		}
		if strings.HasPrefix(out, "-") || strings.HasSuffix(out, "-") || strings.Contains(out, "--") {
			t.Fatalf("bad hyphens: %q -> %q", in, out)
		}
	})
}

func FuzzMake(f *testing.F) {
	f.Add("Hello, World!")
	f.Fuzz(func(t *testing.T, in string) {
		out := Make(in)
		if Make(out) != out {
			t.Fatalf("not idempotent: %q -> %q", in, out)
		}
	})
}
