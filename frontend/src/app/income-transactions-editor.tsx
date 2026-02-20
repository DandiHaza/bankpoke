"use client";

import { useEffect, useRef, useState } from "react";

type IncomeTransactionItem = {
  id?: string;
  date: string;
  category: string;
  description: string;
  amount: number;
  method: string;
  excluded: boolean;
};

type IncomeCategoryTransactions = {
  category: string;
  total_amount: number;
  count: number;
  items: IncomeTransactionItem[];
};

type EditFormState = {
  date: string;
  category: string;
  description: string;
  amount: string;
  method: string;
};

type OriginalItemState = {
  date: string;
  category: string;
  description: string;
  amount: number;
  method: string;
  excluded: boolean;
};

type IncomeTransactionsEditorProps = {
  apiBaseUrl: string;
  groups: IncomeCategoryTransactions[];
};

function formatKrw(value: number): string {
  return new Intl.NumberFormat("ko-KR").format(value);
}

function toSafeId(value: unknown): string {
  if (typeof value === "string") {
    return value.trim();
  }

  if (typeof value === "number") {
    return String(value).trim();
  }

  return "";
}

function regroupIncomeItems(items: IncomeTransactionItem[]): IncomeCategoryTransactions[] {
  const grouped = new Map<string, IncomeTransactionItem[]>();

  for (const item of items) {
    const category = item.category || "미분류";
    const existing = grouped.get(category) ?? [];
    existing.push(item);
    grouped.set(category, existing);
  }

  return Array.from(grouped.entries())
    .map(([category, groupedItems]) => ({
      category,
      items: groupedItems,
      count: groupedItems.length,
      total_amount: groupedItems.reduce((sum, current) => sum + current.amount, 0),
    }))
    .sort((left, right) => right.total_amount - left.total_amount);
}

export default function IncomeTransactionsEditor({
  apiBaseUrl,
  groups,
}: IncomeTransactionsEditorProps) {
  const firstInputRef = useRef<HTMLInputElement | null>(null);
  const [localGroups, setLocalGroups] = useState<IncomeCategoryTransactions[]>(groups);
  const [editingRowKey, setEditingRowKey] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [originalItem, setOriginalItem] = useState<OriginalItemState | null>(null);
  const [form, setForm] = useState<EditFormState | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!editingRowKey || !firstInputRef.current) {
      return;
    }

    firstInputRef.current.focus();
    firstInputRef.current.select();
  }, [editingRowKey]);

  const startEdit = (rowKey: string, item: IncomeTransactionItem) => {
    const normalizedId = toSafeId(item.id);
    setEditingRowKey(rowKey);
    setEditingId(normalizedId ? normalizedId : null);
    setOriginalItem({
      date: item.date,
      category: item.category,
      description: item.description,
      amount: item.amount,
      method: item.method,
      excluded: item.excluded,
    });
    setForm({
      date: item.date,
      category: item.category,
      description: item.description,
      amount: String(item.amount),
      method: item.method,
    });
    setError(null);
  };

  const cancelEdit = () => {
    setEditingRowKey(null);
    setEditingId(null);
    setOriginalItem(null);
    setForm(null);
    setError(null);
  };

  const updateField = (field: keyof EditFormState, value: string) => {
    setForm((previous) => (previous ? { ...previous, [field]: value } : previous));
  };

  const saveEdit = async () => {
    if (!form) {
      return;
    }

    if (!editingId && !originalItem) {
      setError("수정 대상을 찾을 수 없습니다.");
      return;
    }

    const amount = Number.parseInt(form.amount, 10);
    if (Number.isNaN(amount) || amount <= 0) {
      setError("금액은 1 이상 숫자여야 합니다.");
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      const updateBody = {
        date: form.date,
        category: form.category,
        description: form.description,
        amount,
        method: form.method,
      };

      const response = editingId
        ? await fetch(`${apiBaseUrl}/api/income-transactions/${editingId}`, {
            method: "PATCH",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(updateBody),
          })
        : await fetch(`${apiBaseUrl}/api/income-transactions`, {
            method: "PATCH",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              original: originalItem,
              updated: updateBody,
            }),
          });

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        setError(payload?.detail ?? "수정 저장에 실패했습니다.");
        return;
      }

      setLocalGroups((previousGroups) =>
        previousGroups.map((group) => {
          const items = group.items.map((currentItem) => {
            const isTarget = editingId
              ? currentItem.id === editingId
              : originalItem
                ? currentItem.date === originalItem.date &&
                  currentItem.category === originalItem.category &&
                  currentItem.description === originalItem.description &&
                  currentItem.amount === originalItem.amount &&
                  currentItem.method === originalItem.method
                : false;

            if (!isTarget) {
              return currentItem;
            }

            return {
              ...currentItem,
              ...updateBody,
            };
          });

          return {
            ...group,
            items,
            count: items.length,
            total_amount: items.reduce((sum, current) => sum + current.amount, 0),
          };
        }),
      );

      cancelEdit();
    } catch {
      setError("수정 저장 중 네트워크 오류가 발생했습니다.");
    } finally {
      setIsSaving(false);
    }
  };

  const requestExcludedUpdate = async (item: IncomeTransactionItem, excluded: boolean) => {
    const normalizedId = toSafeId(item.id);

    return normalizedId
      ? fetch(`${apiBaseUrl}/api/income-transactions/${normalizedId}`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ excluded }),
        })
      : fetch(`${apiBaseUrl}/api/income-transactions`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            original: {
              date: item.date,
              category: item.category,
              description: item.description,
              amount: item.amount,
              method: item.method,
              excluded: item.excluded,
            },
            updated: { excluded },
          }),
        });
  };

  const toggleExcluded = async (item: IncomeTransactionItem) => {
    setIsSaving(true);
    setError(null);

    try {
      const response = await requestExcludedUpdate(item, !item.excluded);

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        setError(payload?.detail ?? "수입 제외 처리에 실패했습니다.");
        return;
      }

      setLocalGroups((previousGroups) => {
        const nextGroups = previousGroups
          .map((group) => {
            const items = group.items
              .map((groupItem) => {
                const isTarget = item.id
                  ? groupItem.id === item.id
                  : groupItem.date === item.date &&
                    groupItem.category === item.category &&
                    groupItem.description === item.description &&
                    groupItem.amount === item.amount &&
                    groupItem.method === item.method;

                if (!isTarget) {
                  return groupItem;
                }

                return {
                  ...groupItem,
                  excluded: !groupItem.excluded,
                };
              })
              .filter((groupItem) => !groupItem.excluded);

            return {
              ...group,
              items,
              count: items.length,
              total_amount: items.reduce((sum, current) => sum + current.amount, 0),
            };
          })
          .filter((group) => group.items.length > 0)
          .sort((left, right) => right.total_amount - left.total_amount);

        return nextGroups;
      });
    } catch {
      setError("수입 제외 처리 중 네트워크 오류가 발생했습니다.");
    } finally {
      setIsSaving(false);
    }
  };

  const excludeWholeCategory = async (group: IncomeCategoryTransactions) => {
    if (group.items.length === 0) {
      return;
    }

    setIsSaving(true);
    setError(null);

    try {
      for (const item of group.items) {
        const response = await requestExcludedUpdate(item, true);
        if (!response.ok) {
          const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
          setError(payload?.detail ?? "대분류 전체 제외 처리에 실패했습니다.");
          return;
        }
      }

      setLocalGroups((previousGroups) => previousGroups.filter((currentGroup) => currentGroup.category !== group.category));

      if (editingRowKey?.startsWith(`${group.category}:`)) {
        cancelEdit();
      }
    } catch {
      setError("대분류 전체 제외 처리 중 네트워크 오류가 발생했습니다.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div style={{ display: "grid", gap: 10 }}>
      {localGroups.map((group) => (
        <details key={group.category}>
          <summary style={{ cursor: "pointer", fontWeight: 700 }}>
            {group.category} · {formatKrw(group.total_amount)}원 · {group.count}건
          </summary>
          <div style={{ marginTop: 8 }}>
            <button
              type="button"
              onClick={() => excludeWholeCategory(group)}
              disabled={isSaving}
              style={{
                background: "#b63a3a",
                color: "#ffffff",
                border: "none",
                borderRadius: 6,
                padding: "4px 10px",
                cursor: "pointer",
                opacity: isSaving ? 0.7 : 1,
              }}
            >
              대분류 전체 제외
            </button>
          </div>
          <ul style={{ margin: "8px 0 0", paddingLeft: 20, display: "grid", gap: 8 }}>
            {group.items.map((item, index) => {
              const rowKey = `${group.category}:${item.id ?? "missing-id"}:${index}`;
              const editing = editingRowKey === rowKey;
              return (
                <li key={rowKey}>
                  {editing && form ? (
                    <div style={{ display: "grid", gap: 6 }}>
                      <input
                        ref={firstInputRef}
                        type="date"
                        value={form.date}
                        onChange={(event) => updateField("date", event.target.value)}
                      />
                      <input
                        value={form.category}
                        onChange={(event) => updateField("category", event.target.value)}
                      />
                      <input
                        value={form.description}
                        onChange={(event) => updateField("description", event.target.value)}
                      />
                      <input value={form.amount} onChange={(event) => updateField("amount", event.target.value)} />
                      <input value={form.method} onChange={(event) => updateField("method", event.target.value)} />
                      <div style={{ display: "flex", gap: 8 }}>
                        <button type="button" onClick={saveEdit} disabled={isSaving}>
                          {isSaving ? "저장 중..." : "저장"}
                        </button>
                        <button type="button" onClick={cancelEdit} disabled={isSaving}>
                          취소
                        </button>
                      </div>
                      {error ? <p style={{ margin: 0, color: "#b63a3a" }}>{error}</p> : null}
                    </div>
                  ) : (
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <span style={{ flex: 1 }}>
                        {item.date} · {item.description} · {formatKrw(item.amount)}원
                        {item.method ? ` · ${item.method}` : ""}
                        {item.excluded ? " · 제외됨" : ""}
                      </span>
                      <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
                        <button
                          type="button"
                          onClick={() => startEdit(rowKey, item)}
                          style={{
                            background: "#1d7a46",
                            color: "#ffffff",
                            border: "none",
                            borderRadius: 6,
                            padding: "4px 10px",
                            cursor: "pointer",
                          }}
                        >
                          수정
                        </button>
                        <button
                          type="button"
                          onClick={() => toggleExcluded(item)}
                          disabled={isSaving}
                          style={{
                            background: item.excluded ? "#6b7280" : "#d14343",
                            color: "#ffffff",
                            border: "none",
                            borderRadius: 6,
                            padding: "4px 10px",
                            cursor: "pointer",
                            opacity: isSaving ? 0.7 : 1,
                          }}
                        >
                          {item.excluded ? "제외 해제" : "수입에서 제외"}
                        </button>
                      </div>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </details>
      ))}
    </div>
  );
}
