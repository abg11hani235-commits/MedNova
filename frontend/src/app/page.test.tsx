import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import HomePage from "./page";

describe("HomePage", () => {
  it("renders Clinsight title", () => {
    render(<HomePage />);
    const headings = screen.getAllByText("Clinsight");
    expect(headings.length).toBeGreaterThan(0);
  });
});
