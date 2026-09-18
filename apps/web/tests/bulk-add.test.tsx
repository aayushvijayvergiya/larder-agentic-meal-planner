import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BulkAdd, parseBulk } from "@/components/pantry/BulkAdd";

describe("BulkAdd", () => {
  it("parses commas and newlines", () => {
    expect(parseBulk("Paneer, spinach\n toor dal,, Spinach")).toEqual(["Paneer", "spinach", "toor dal"]);
    expect(parseBulk("")).toEqual([]);
  });

  it("submits parsed names and clears", () => {
    const onAdd = vi.fn();
    render(<BulkAdd onAdd={onAdd} />);
    const box = screen.getByTestId("bulk-add");
    fireEvent.change(box, { target: { value: "onion, tomato" } });
    expect(screen.getByTestId("bulk-add-submit")).toHaveTextContent("Add 2 items");
    fireEvent.click(screen.getByTestId("bulk-add-submit"));
    expect(onAdd).toHaveBeenCalledWith(["onion", "tomato"]);
    expect(box).toHaveValue("");
  });
});
