import type { PlanEntryOut } from "@larder/api-client";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PlanEntryCard } from "@/components/plan/PlanEntryCard";

const entry = {
  id: "e",
  date: "2026-09-18",
  slot_key: "dinner",
  slot_label: "Dinner",
  reason: "Uses the spinach you have.",
  covered_ingredients: ["spinach"],
  missing_ingredients: [{ name: "cream", category: "dairy", is_optional: true }],
  variations: [{ member_id: "m", display_name: "Aarav", note: "no green chilli" }],
  my_feedback: "up",
  cooked_count: 0,
  meal: { id: "meal", name: "Palak paneer" },
} as unknown as PlanEntryOut;

describe("PlanEntryCard", () => {
  it("renders reason, coverage, variations and feedback state", () => {
    const onFeedback = vi.fn();
    const onSwap = vi.fn();
    render(<PlanEntryCard entry={entry} onSwap={onSwap} onFeedback={onFeedback} />);
    expect(screen.getByText("Palak paneer")).toBeInTheDocument();
    expect(screen.getByText(/Uses the spinach/)).toBeInTheDocument();
    expect(screen.getByText(/cream \(optional\)/)).toBeInTheDocument();
    expect(screen.getByText(/no green chilli/)).toBeInTheDocument();
    expect(screen.getByLabelText("Thumbs up")).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByTestId("cooked"));
    expect(onFeedback).toHaveBeenCalledWith("cooked");
    fireEvent.click(screen.getByTestId("swap"));
    expect(onSwap).toHaveBeenCalled();
  });

  it("compact mode hides reason and actions", () => {
    render(<PlanEntryCard entry={entry} compact onSwap={() => {}} onFeedback={() => {}} />);
    expect(screen.queryByText(/Uses the spinach/)).not.toBeInTheDocument();
    expect(screen.queryByTestId("swap")).not.toBeInTheDocument();
  });
});
