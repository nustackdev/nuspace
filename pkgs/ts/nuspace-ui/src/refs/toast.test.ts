import { toast } from "@nustackdev/ui-kit";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { typePath } from "../core/surfaces";
import { notifyOp } from "../core/wire";
import { applyToastWrite, deletedCells, deletedPlane } from "./toast";

vi.mock("@nustackdev/ui-kit", async (real) => ({
	...(await real<typeof import("@nustackdev/ui-kit")>()),
	toast: vi.fn(),
}));
vi.mock("../core/wire", () => ({ notifyOp: vi.fn() }));
vi.mock("../core/surfaces", () => ({ typePath: vi.fn() }));

/** The action of the one toast shown, clicked. */
function undo(): void {
	const [[shown]] = vi.mocked(toast).mock.calls;
	shown.action?.onClick();
}

describe("ToastRef", () => {
	beforeEach(() => vi.clearAllMocks());

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

	it("toasts a cells delete with an Undo sent on the toaster's own path", () => {
		vi.mocked(typePath).mockReturnValue(["shell", "toast"]);
		deletedCells(["a", "b"]);
		expect(vi.mocked(toast).mock.calls[0][0].title).toBe("2 cells deleted");
		undo();
		expect(notifyOp).toHaveBeenCalledWith(["shell", "toast"], "cell.restore", {
			cell_ids: ["a", "b"],
		});
	});

	it("says one cell, and a plane's delete undoes by its id", () => {
		vi.mocked(typePath).mockReturnValue(["toast"]);
		deletedCells(["a"]);
		expect(vi.mocked(toast).mock.calls[0][0].title).toBe("Cell deleted");
		vi.mocked(toast).mockClear();
		deletedPlane("p", "Notes");
		expect(vi.mocked(toast).mock.calls[0][0]).toMatchObject({
			title: "Plane deleted",
			description: "Notes",
		});
		undo();
		expect(notifyOp).toHaveBeenCalledWith(["toast"], "plane.restore", { plane_id: "p" });
	});

	it("toasts nothing for no cells", () => {
		deletedCells([]);
		expect(toast).not.toHaveBeenCalled();
	});
});
