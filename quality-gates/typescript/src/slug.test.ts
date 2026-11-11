import * as fc from "fast-check";
import { describe, expect, it } from "vitest";
import { makeSlug } from "./slug";

describe("makeSlug", () => {
  it("is idempotent and never produces leading, trailing, or doubled hyphens", () => {
    fc.assert(
      fc.property(fc.string(), (input) => {
        const slug = makeSlug(input);
        expect(makeSlug(slug)).toBe(slug);
        expect(slug).not.toMatch(/^-|-$|--/);
      }),
    );
  });
});
