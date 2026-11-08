import { toast } from "@nustackdev/ui-kit";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { applyToastWrite } from "./toast";

vi.mock("@nustackdev/ui-kit", async (real) => ({
	...(await real<typeof import("@nustackdev/ui-kit")>()),
	toast: vi.fn(),
}));

describe("ToastRef", () => {
	beforeEach(() => vi.mocked(toast).mockClear());

	it("shows a failed interaction's type and message as a danger toast", () => {
		applyToastWrite({ op: "show", type: "Refused", message: "plane home is a system plane" });
		expect(toast).toHaveBeenCalledExactlyOnceWith({
			tone: "danger",
			title: "Refused",
			description: "plane home is a system plane",
		});
	});

	it("ignores any other write", () => {
		applyToastWrite({ op: "noise" });
		applyToastWrite(null);
		expect(toast).not.toHaveBeenCalled();
	});
});
