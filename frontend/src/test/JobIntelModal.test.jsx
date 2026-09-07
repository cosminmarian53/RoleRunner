import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import JobIntelModal from "../components/JobIntelModal";

vi.mock("../lib/api", () => ({
  api: vi.fn().mockResolvedValue({
    role_summary: "Core role leading payments infrastructure.",
    framing_strategy: "Emphasize high throughput and fault-tolerant architecture.",
    company_insights: "Fast-paced, engineering-led culture with deep focus on reliability.",
    culture_notes: "Extreme customer focus and operational excellence.",
    scraped_source: "https://stripe.com/jobs/123",
    interview_stages: [
      "1. Recruiter Screen (30m)",
      "2. Technical Execution (60m)",
    ],
    study_guide: [
      {
        topic: "Distributed Consensus",
        key_concepts: "Raft, Paxos, leader election",
        practice_focus: "Build mini Raft node",
      },
    ],
    improvement_suggestions: [
      "Highlight distributed database experience",
    ],
    how_to_land_role: [
      "Step 1: Pitch past telemetry scale",
    ],
    likely_interview_questions: [
      {
        question: "How do you handle idempotency in payment APIs?",
        why_they_ask: "Assessing double-charge prevention.",
        recommended_angle: "Explain unique idempotency keys in Redis + transactional outbox.",
      },
    ],
    talking_points: ["Scaled pipeline to 50k RPS"],
    questions_to_ask: ["What does team on-call look like?"],
  }),
}));

describe("JobIntelModal Component", () => {
  const sampleJob = {
    title: "Senior Backend Engineer",
    company: "Stripe",
    location: "Remote",
    link: "https://stripe.com/jobs/123",
  };

  it("renders modal header, live scraped badge, and export guide button", async () => {
    render(<JobIntelModal job={sampleJob} onClose={vi.fn()} />);

    expect(screen.getByText("Senior Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Stripe")).toBeInTheDocument();

    // Wait for intelligence data to render
    const framing = await screen.findByText(/Emphasize high throughput and fault-tolerant architecture/i);
    expect(framing).toBeInTheDocument();

    expect(screen.getByText(/Live Web Scraped/i)).toBeInTheDocument();
    expect(screen.getByText(/Export Guide \(\.md\)/i)).toBeInTheDocument();
  });

  it("renders study guide, suggestions, and interview questions", async () => {
    render(<JobIntelModal job={sampleJob} onClose={vi.fn()} />);

    // Check study guide
    const studySection = await screen.findByText(/What to Study & Technical Prep Guide/i);
    expect(studySection).toBeInTheDocument();
    expect(screen.getByText("Distributed Consensus")).toBeInTheDocument();
    expect(screen.getByText(/Raft, Paxos, leader election/i)).toBeInTheDocument();

    // Check likely questions
    expect(screen.getByText(/How do you handle idempotency in payment APIs\?/i)).toBeInTheDocument();
    expect(screen.getByText(/Assessing double-charge prevention/i)).toBeInTheDocument();

    // Check playbook
    expect(screen.getByText(/Step 1: Pitch past telemetry scale/i)).toBeInTheDocument();
  });

  it("triggers export guide markdown download when clicked", async () => {
    const createObjectUrlMock = vi.fn().mockReturnValue("blob:mock-url");
    const revokeObjectUrlMock = vi.fn();
    global.URL.createObjectURL = createObjectUrlMock;
    global.URL.revokeObjectURL = revokeObjectUrlMock;

    render(<JobIntelModal job={sampleJob} onClose={vi.fn()} />);

    const exportBtn = await screen.findByText(/Export Guide \(\.md\)/i);
    fireEvent.click(exportBtn);

    expect(createObjectUrlMock).toHaveBeenCalled();
    expect(revokeObjectUrlMock).toHaveBeenCalled();
  });
});
