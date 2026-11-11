package slug

import (
	"strings"
	"unicode"
)

// Make lowercases s and joins runs of letters and digits with single hyphens.
func Make(s string) string {
	var b strings.Builder
	pendingHyphen := false
	for _, r := range strings.ToLower(s) {
		if unicode.IsLetter(r) || unicode.IsDigit(r) {
			if pendingHyphen && b.Len() > 0 {
				b.WriteByte('-')
			}
			pendingHyphen = false
			b.WriteRune(r)
			continue
		}
		pendingHyphen = true
	}
	return b.String()
}
