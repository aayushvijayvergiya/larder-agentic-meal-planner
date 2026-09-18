import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MealForm, parseIngredients } from "@/components/meals/MealForm";

describe("MealForm", () => {
  it("parses ingredient lines and submits", () => {
    expect(parseIngredients("spinach\npaneer, Spinach")).toEqual(["spinach", "paneer"]);
    const onSubmit = vi.fn();
    render(<MealForm onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Palak paneer" } });
    fireEvent.change(screen.getByLabelText("Ingredients"), { target: { value: "spinach\npaneer" } });
    fireEvent.click(screen.getByText("Save meal"));
    expect(onSubmit).toHaveBeenCalledWith({ name: "Palak paneer", description: null, ingredients: ["spinach", "paneer"], instructions: null });
  });
});
