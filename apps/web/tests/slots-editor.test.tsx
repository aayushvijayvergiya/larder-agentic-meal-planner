import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SlotsEditor } from "@/components/household/SlotsEditor";

const slots = [
  { key: "dinner", label: "Dinner", order: 2 },
  { key: "lunch", label: "Lunch", order: 1 },
];

describe("SlotsEditor", () => {
  it("prevents duplicate keys and emits slots renumbered by order", () => {
    const onSave = vi.fn();
    render(<SlotsEditor slots={slots} onSave={onSave} />);
    fireEvent.change(screen.getByLabelText("Add a slot"), { target: { value: "Lunch" } });
    expect(screen.getByText("That slot already exists")).toBeInTheDocument();
    expect(screen.getByText("Add")).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Add a slot"), { target: { value: "Evening tea" } });
    fireEvent.click(screen.getByText("Add"));
    fireEvent.click(screen.getByLabelText("Move Evening tea up"));
    fireEvent.click(screen.getByTestId("save-slots"));
    expect(onSave).toHaveBeenCalledWith([
      { key: "lunch", label: "Lunch", order: 1 },
      { key: "evening_tea", label: "Evening tea", order: 2 },
      { key: "dinner", label: "Dinner", order: 3 },
    ]);
  });
});
