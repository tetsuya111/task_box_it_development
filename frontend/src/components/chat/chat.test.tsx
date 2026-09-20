import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import type { PromptTemplate } from "@/lib/types";
import { ActionBar } from "./ActionBar";
import { Composer } from "./Composer";
import { AgentCallDialog, FinalizeDialog } from "./dialogs";
import { MessageBubble } from "./MessageBubble";

const TEMPLATES: PromptTemplate[] = [
  { id: 1, label: "見積もり（相場）", prompt: "相場の見積もりをして。" },
  { id: 2, label: "アイデアを出して", prompt: "アイデアを出力して" },
];

function ComposerHarness({ onSend, disabled = false }: { onSend: () => void; disabled?: boolean }) {
  const [value, setValue] = useState("");
  return <Composer value={value} onChange={setValue} onSend={onSend} templates={TEMPLATES} disabled={disabled} />;
}

describe("Composer", () => {
  it("テンプレを選ぶとテキストボックスに入るだけで、送信はされず、編集できる", async () => {
    const onSend = vi.fn();
    render(<ComposerHarness onSend={onSend} />);
    await userEvent.selectOptions(screen.getByLabelText("テンプレ"), "見積もり（相場）");
    const textbox = screen.getByLabelText("メッセージ");
    expect(textbox).toHaveValue("相場の見積もりをして。");
    expect(onSend).not.toHaveBeenCalled();

    await userEvent.type(textbox, "ざっくりで");
    expect(textbox).toHaveValue("相場の見積もりをして。ざっくりで");
    await userEvent.click(screen.getByRole("button", { name: "送信" }));
    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it("処理中は入力も送信もできない", () => {
    render(<ComposerHarness onSend={vi.fn()} disabled />);
    expect(screen.getByLabelText("メッセージ")).toBeDisabled();
    expect(screen.getByLabelText("テンプレ")).toBeDisabled();
    expect(screen.getByRole("button", { name: "送信" })).toBeDisabled();
  });
});

describe("ActionBar", () => {
  it("仕様どおりの名前の5つのボタンがあり、処理中はすべて無効になる", async () => {
    const onAction = vi.fn();
    const { rerender } = render(<ActionBar disabled={false} onAction={onAction} />);
    const labels = ["要件の確定", "相場見積もり", "自分見積もり", "現状の要約のDL", "クリア"];
    expect(screen.getAllByRole("button").map((button) => button.textContent)).toEqual(labels);
    await userEvent.click(screen.getByRole("button", { name: "自分見積もり" }));
    expect(onAction).toHaveBeenCalledWith("self-estimate");

    rerender(<ActionBar disabled onAction={onAction} />);
    screen.getAllByRole("button").forEach((button) => expect(button).toBeDisabled());
  });
});

describe("MessageBubble", () => {
  const base = { role: "assistant", kind: "agent_result", content: "合計: 5万円" } as const;

  it("見積もりには固定の注意書きを付ける", () => {
    render(<MessageBubble message={{ ...base, metadata: { agent_name: "自分見積もり", is_estimate: true } }} />);
    expect(screen.getByText(/AIによる自動的な見積もりです/)).toBeInTheDocument();
    expect(screen.getByText("自分見積もり")).toBeInTheDocument();
  });

  it("プレビューには仮の値である旨と、補完した項目を表示する", () => {
    render(
      <MessageBubble
        message={{ ...base, metadata: { agent_name: "要件サマリーのプレビュー", is_preview: true, completed_items: ["予算のレンジ", "セキュリティ"] } }}
      />,
    );
    expect(screen.getByText(/仮の値を含むプレビューです/)).toBeInTheDocument();
    expect(screen.getByText(/予算のレンジ、セキュリティ/)).toBeInTheDocument();
  });

  it("通常の応答には注意書きを付けない", () => {
    render(<MessageBubble message={{ role: "assistant", kind: "chat", content: "いいですね", metadata: {} }} />);
    expect(screen.queryByText(/AIによる自動的な見積もりです/)).not.toBeInTheDocument();
  });

  it("本文の生のHTMLは解釈しない", () => {
    const { container } = render(
      <MessageBubble message={{ role: "assistant", kind: "chat", content: "<img src=x onerror=alert(1)>**太字**", metadata: {} }} />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("strong")).toHaveTextContent("太字");
  });

  it("htmlのコードブロックは、スクリプトを実行できない隔離した枠に表示する", () => {
    render(
      <MessageBubble
        message={{ role: "assistant", kind: "chat", content: "```html\n<script>alert(1)</script><h1>予約</h1>\n```", metadata: {} }}
      />,
    );
    const frame = screen.getByTitle("画面のイメージ");
    expect(frame.tagName).toBe("IFRAME");
    expect(frame.getAttribute("sandbox")).toBe("");
    expect(frame.getAttribute("srcdoc")).toContain("Content-Security-Policy");
    expect(frame.getAttribute("srcdoc")).toContain("default-src 'none'");
  });
});

describe("AgentCallDialog", () => {
  it("どのエージェントかを示し、「はい / いいえ」を返す", async () => {
    const onAnswer = vi.fn();
    render(<AgentCallDialog call={{ id: 1, agent_key: "market_estimate", agent_name: "相場見積もり" }} disabled={false} onAnswer={onAnswer} />);
    expect(screen.getByRole("dialog")).toHaveTextContent("相場見積もり");
    await userEvent.click(screen.getByRole("button", { name: "いいえ" }));
    await userEvent.click(screen.getByRole("button", { name: "はい" }));
    expect(onAnswer.mock.calls).toEqual([[false], [true]]);
  });
});

describe("FinalizeDialog", () => {
  const summary = { id: 7, title: "予約管理ツール", body_markdown: "# 目的\n<b>予約</b>" };

  it("そろっていない項目を一覧で表示する", () => {
    render(<FinalizeDialog state={{ kind: "missing", missing: ["予算のレンジ"] }} disabled={false} error="" onSubmit={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByRole("listitem")).toHaveTextContent("予算のレンジ");
  });

  it("要件サマリーをテキストのまま表示し、「確定」「修正」を出す", () => {
    const onSubmit = vi.fn();
    const onClose = vi.fn();
    const { container } = render(<FinalizeDialog state={{ kind: "summary", summary }} disabled={false} error="" onSubmit={onSubmit} onClose={onClose} />);
    expect(container.querySelector("pre")?.textContent).toBe("# 目的\n<b>予約</b>");
    expect(container.querySelector("pre b")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "確定" }));
    fireEvent.click(screen.getByRole("button", { name: "修正" }));
    expect(onSubmit).toHaveBeenCalledWith(summary);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("送信後は案内を表示する", () => {
    render(<FinalizeDialog state={{ kind: "submitted", notice: "管理者からのメールをお待ちください" }} disabled={false} error="" onSubmit={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByRole("dialog")).toHaveTextContent("管理者からのメールをお待ちください");
  });
});
