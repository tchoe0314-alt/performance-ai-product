import { expect, test } from "@playwright/test";

import { blankCanvasNextAction } from "../../app/components/PreviewBlankCanvasActions";

test("blank canvas guidance distinguishes missing site scale from an empty scaled site", () => {
  expect(blankCanvasNextAction(false)).toBe(
    "Next: enter an address or draw the boundary to establish site scale.",
  );
  expect(blankCanvasNextAction(true)).toBe(
    "Next: draw the boundary, then add the first design object.",
  );
});
