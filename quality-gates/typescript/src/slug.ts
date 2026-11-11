export function makeSlug(input: string): string {
  return input
    .toLowerCase()
    .split(/[^\p{L}\p{N}]+/u)
    .filter((part) => part.length > 0)
    .join("-");
}
