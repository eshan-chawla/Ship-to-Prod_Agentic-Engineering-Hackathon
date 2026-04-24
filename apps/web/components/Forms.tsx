"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState, useTransition } from "react";
import { browserBaseUrl } from "@/lib/api";

async function post(path: string, body?: unknown) {
  const response = await fetch(`${browserBaseUrl}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed with ${response.status}`);
  }
}

export function SupplierForm() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError("");
    try {
      await post("/suppliers", Object.fromEntries(form));
      event.currentTarget.reset();
      startTransition(() => router.refresh());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Unable to create supplier");
    }
  }

  return (
    <form onSubmit={onSubmit} className="panel grid gap-3 p-5 md:grid-cols-2">
      <input required name="name" className="field" placeholder="Supplier name" />
      <input required name="website" className="field" placeholder="Website" />
      <input required name="country" className="field" placeholder="Country" />
      <input required name="category" className="field" placeholder="Category" />
      <select name="criticality" className="field md:col-span-2" defaultValue="medium">
        <option value="low">Low criticality</option>
        <option value="medium">Medium criticality</option>
        <option value="high">High criticality</option>
        <option value="critical">Critical supplier</option>
      </select>
      {error ? <p className="text-sm font-black text-clay md:col-span-2">{error}</p> : null}
      <button disabled={pending} className="btn md:col-span-2">{pending ? "Adding..." : "Add supplier"}</button>
    </form>
  );
}

export function ProductForm() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload = {
      name: String(form.get("name")),
      brand: String(form.get("brand")),
      category: String(form.get("category")),
      target_price: Number(form.get("target_price")),
      target_margin: Number(form.get("target_margin"))
    };
    setError("");
    try {
      await post("/products", payload);
      event.currentTarget.reset();
      startTransition(() => router.refresh());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Unable to create product");
    }
  }

  return (
    <form onSubmit={onSubmit} className="panel grid gap-3 p-5 md:grid-cols-2">
      <input required name="name" className="field" placeholder="Product name" />
      <input required name="brand" className="field" placeholder="Brand" />
      <input required name="category" className="field" placeholder="Category" />
      <input required name="target_price" type="number" step="0.01" className="field" placeholder="Target price" />
      <input required name="target_margin" type="number" step="0.01" min="0" max="1" className="field md:col-span-2" placeholder="Target margin, e.g. 0.32" />
      {error ? <p className="text-sm font-black text-clay md:col-span-2">{error}</p> : null}
      <button disabled={pending} className="btn md:col-span-2">{pending ? "Adding..." : "Add product"}</button>
    </form>
  );
}

export function CompetitorForm({ productId }: { productId: number }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError("");
    try {
      await post(`/products/${productId}/competitors`, Object.fromEntries(form));
      event.currentTarget.reset();
      startTransition(() => router.refresh());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Unable to add competitor");
    }
  }

  return (
    <form onSubmit={onSubmit} className="panel grid gap-3 p-5">
      <input required name="competitor_name" className="field" placeholder="Competitor name" />
      <input required name="url" className="field" placeholder="Competitor URL" />
      {error ? <p className="text-sm font-black text-clay">{error}</p> : null}
      <button disabled={pending} className="btn">{pending ? "Adding..." : "Add competitor URL"}</button>
    </form>
  );
}

export function ScanButton({ path, label }: { path: string; label: string }) {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [pending, startTransition] = useTransition();

  async function run() {
    setMessage("");
    try {
      await post(path);
      setMessage("Queued. Worker will write results shortly.");
      startTransition(() => router.refresh());
    } catch (exc) {
      setMessage(exc instanceof Error ? exc.message : "Unable to queue scan");
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <button type="button" disabled={pending} onClick={run} className="btn btn-secondary">
        {pending ? "Queueing..." : label}
      </button>
      {message ? <p className="text-xs font-black text-ink/65">{message}</p> : null}
    </div>
  );
}

