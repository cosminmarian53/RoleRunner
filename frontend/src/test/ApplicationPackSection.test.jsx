import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ApplicationPackSection from "../components/ApplicationPackSection";

describe("ApplicationPackSection Component", () => {
  const samplePack = {
    job_title: "Staff Software Engineer",
    company: "Stripe",
    apply_url: "https://stripe.com/jobs/123",
    cover_note: "Excited to apply to Stripe.",
    standard_fields: {
      "Full Name": "Cosmin Lavric",
      "Email": "cosmin@example.com",
      "Current Location": "Brasov, Romania",
    },
    custom_questions: [
      {
        field_id: "q1",
        label: "Why Stripe?",
        field_type: "textarea",
        required: true,
        suggested_answer: "Passionate about economic infrastructure and distributed systems.",
      },
      {
        field_id: "q2",
        label: "Years of Experience?",
        field_type: "text",
        required: false,
        suggested_answer: "4+ years",
      },
    ],
  };

  it("renders cover note and question list properly", () => {
    const copyMock = vi.fn();
    const setPackMock = vi.fn();

    render(
      <ApplicationPackSection
        appPack={samplePack}
        setAppPack={setPackMock}
        jobUrl={samplePack.apply_url}
        copiedField=""
        copyToClipboard={copyMock}
      />
    );

    expect(screen.getByText(/Universal Master Application Pack/i)).toBeInTheDocument();
    expect(screen.getByText("Why Stripe?")).toBeInTheDocument();
    expect(screen.getByText("Years of Experience?")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Excited to apply to Stripe.")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Passionate about economic infrastructure and distributed systems.")).toBeInTheDocument();
  });

  it("handles answer change with immutable state update", () => {
    const setPackMock = vi.fn();

    render(
      <ApplicationPackSection
        appPack={samplePack}
        setAppPack={setPackMock}
        jobUrl={samplePack.apply_url}
        copiedField=""
        copyToClipboard={vi.fn()}
      />
    );

    const input = screen.getByDisplayValue("4+ years");
    fireEvent.change(input, { target: { value: "5 years" } });

    expect(setPackMock).toHaveBeenCalled();
  });

  it("calls copyToClipboard when Copy button is clicked", () => {
    const copyMock = vi.fn();

    render(
      <ApplicationPackSection
        appPack={samplePack}
        setAppPack={vi.fn()}
        jobUrl={samplePack.apply_url}
        copiedField=""
        copyToClipboard={copyMock}
      />
    );

    const copyButtons = screen.getAllByRole("button", { name: /Copy/i });
    expect(copyButtons.length).toBeGreaterThan(0);
    fireEvent.click(copyButtons[0]);

    expect(copyMock).toHaveBeenCalled();
  });
});
