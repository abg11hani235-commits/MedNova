import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import HomePage from "./page";

describe("HomePage", () => {
  it("renders Rafiq title", () => {
    render(<HomePage />);
    const headings = screen.getAllByText("Rafiq");
    expect(headings.length).toBeGreaterThan(0);
  });

});
