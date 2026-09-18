import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WidgetRenderer } from "@/components/onboarding/WidgetRenderer";

describe("WidgetRenderer", () => {
  it("submits the right value shape per widget", () => {
    const onSubmit = vi.fn();
    const { rerender } = render(<WidgetRenderer widget={{ type: "number", unit: "cm", min: 50, max: 250, step: 1 }} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "172" } });
    fireEvent.click(screen.getByText("Continue"));
    expect(onSubmit).toHaveBeenLastCalledWith({ kind: "widget", value: 172 });

    rerender(
      <WidgetRenderer
        widget={{ type: "multi_select", options: [{ value: "a", label: "A" }, { value: "b", label: "B" }], allow_custom: false, min: 0, max: 5 }}
        onSubmit={onSubmit}
      />,
    );
    fireEvent.click(screen.getByText("A"));
    fireEvent.click(screen.getByText("B"));
    fireEvent.click(screen.getByText("Continue"));
    expect(onSubmit).toHaveBeenLastCalledWith({ kind: "widget", value: ["a", "b"] });

    rerender(<WidgetRenderer widget={{ type: "text", placeholder: "", multiline: false, max_length: 40 }} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByText("Type instead"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "hi" } });
    fireEvent.click(screen.getByText("Send"));
    expect(onSubmit).toHaveBeenLastCalledWith({ kind: "text", text: "hi" });
  });

  it("single select needs a choice, chips submit none when empty", () => {
    const onSubmit = vi.fn();
    const { rerender } = render(
      <WidgetRenderer widget={{ type: "single_select", options: [{ value: "female", label: "Female" }] }} onSubmit={onSubmit} />,
    );
    expect(screen.getByText("Continue")).toBeDisabled();
    fireEvent.click(screen.getByText("Female"));
    fireEvent.click(screen.getByText("Continue"));
    expect(onSubmit).toHaveBeenLastCalledWith({ kind: "widget", value: "female" });

    rerender(<WidgetRenderer widget={{ type: "chips", suggestions: ["none", "PCOS"], placeholder: "", max: 10 }} onSubmit={onSubmit} />);
    fireEvent.click(screen.getByText("None, continue"));
    expect(onSubmit).toHaveBeenLastCalledWith({ kind: "widget", value: ["none"] });
    fireEvent.change(screen.getByPlaceholderText("Add items, separated by commas"), { target: { value: "thyroid, gout" } });
    fireEvent.click(screen.getByText("Add"));
    fireEvent.click(screen.getByText("Continue"));
    expect(onSubmit).toHaveBeenLastCalledWith({ kind: "widget", value: ["thyroid", "gout"] });
  });

  it("date widget submits an ISO string", () => {
    const onSubmit = vi.fn();
    render(<WidgetRenderer widget={{ type: "date", min: "1900-01-01", max: "2021-01-01" }} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByDisplayValue(""), { target: { value: "1995-04-02" } });
    fireEvent.click(screen.getByText("Continue"));
    expect(onSubmit).toHaveBeenLastCalledWith({ kind: "widget", value: "1995-04-02" });
  });
});
