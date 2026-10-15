"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Compass, Rocket, Search, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { COUNTRIES, COUNTRY_FLAGS } from "@/lib/countries";

export default function Home() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [customDestination, setCustomDestination] = useState("");
  const [launching, setLaunching] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return COUNTRIES;
    return COUNTRIES.filter((c) => c.toLowerCase().includes(q));
  }, [query]);

  function startChat(country: string) {
    router.push(
      `/chat?country=${encodeURIComponent(country)}&v=${crypto.randomUUID()}`,
    );
  }

  function handleCustomSubmit(e: React.FormEvent) {
    e.preventDefault();
    const value = customDestination.trim();
    if (!value || launching) return;
    setLaunching(true);
    startChat(value);
  }

  return (
    <div className="flex min-h-full flex-1 flex-col">
      <header className="sticky top-0 z-20 w-full border-b-2 border-ink bg-cream/95 backdrop-blur-sm">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <div className="flex items-center gap-2.5">
            <span className="flex size-9 items-center justify-center rounded-lg border-2 border-ink bg-sunshine text-lg shadow-[2px_2px_0px_var(--ink)]">
              🧭
            </span>
            <span className="font-heading text-lg font-extrabold tracking-tight text-ink">
              Companion AI
            </span>
          </div>
          <span className="hidden items-center rounded-full border-2 border-ink bg-mint-soft px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider text-ink sm:inline-flex">
            Beta
          </span>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-10 px-4 py-10 sm:px-6 sm:py-14">
        <section className="flex flex-col gap-3">
          <span className="inline-flex w-fit items-center gap-1.5 rounded-full border-2 border-ink bg-cyan-soft px-3 py-1 text-xs font-bold uppercase tracking-wider text-ink">
            <Sparkles className="size-3.5" />
            {COUNTRIES.length}+ worlds to explore
          </span>
          <h1 className="font-heading text-4xl font-extrabold tracking-tight text-ink sm:text-5xl">
            Where are we adventuring{" "}
            <span className="inline-block -rotate-1 rounded-lg border-2 border-ink bg-sunshine px-2 py-0.5 shadow-[3px_3px_0px_var(--ink)]">
              today?
            </span>
          </h1>
          <p className="max-w-2xl text-base font-medium text-muted-foreground sm:text-lg">
            Pick any country and jump into an open-ended chat with your AI guide
            : culture, food, history, nature, or whatever curiosity strikes.
          </p>
        </section>

        <section className="flex flex-col gap-4 rounded-xl border-2 border-ink bg-white p-4 shadow-[4px_4px_0px_var(--ink)] sm:p-5">
          <div className="relative flex items-center">
            <Search className="pointer-events-none absolute left-3.5 size-4 text-outline" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search a country (e.g. Japan, Peru, Kenya)..."
              className="pl-10 pr-10"
            />
            {query.length > 0 && (
              <button
                type="button"
                aria-label="Clear search"
                onClick={() => setQuery("")}
                className="absolute right-3 text-outline hover:text-ink"
              >
                <X className="size-4" />
              </button>
            )}
          </div>
        </section>

        {filtered.length > 0 ? (
          <section className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {filtered.map((country) => (
              <button
                key={country}
                onClick={() => startChat(country)}
                className="group flex flex-col items-center gap-2 rounded-xl border-2 border-ink bg-white p-4 text-center shadow-[3px_3px_0px_var(--ink)] transition-all hover:-translate-x-0.5 hover:-translate-y-0.5 hover:bg-sunshine hover:shadow-[5px_5px_0px_var(--ink)] active:translate-x-[1px] active:translate-y-[1px] active:shadow-[1px_1px_0px_var(--ink)]"
              >
                <span className="text-3xl">
                  {COUNTRY_FLAGS[country] ?? "🌍"}
                </span>
                <span className="font-heading text-sm font-bold text-ink">
                  {country}
                </span>
                <span className="flex items-center gap-1 text-xs font-bold text-ink/60 opacity-0 transition-opacity group-hover:opacity-100">
                  Explore <ArrowRight className="size-3" />
                </span>
              </button>
            ))}
          </section>
        ) : (
          <section className="flex flex-col items-center gap-2 rounded-xl border-2 border-ink bg-white p-10 text-center shadow-[4px_4px_0px_var(--ink)]">
            <span className="text-3xl">🗺️</span>
            <p className="font-heading text-lg font-bold text-ink">
              No match in the quick list
            </p>
            <p className="max-w-md text-sm font-medium text-muted-foreground">
              No worries — type it below and your companion will take you there
              anyway.
            </p>
          </section>
        )}

        <section className="relative overflow-hidden rounded-xl border-2 border-ink bg-cyan-soft p-6 shadow-[4px_4px_0px_var(--ink)] sm:p-8">
          <div className="relative z-10 flex flex-col items-start gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex max-w-xl flex-col gap-1.5">
              <span className="inline-flex w-fit items-center gap-1.5 rounded-full border-2 border-ink bg-white px-2.5 py-0.5 text-xs font-bold text-ink">
                ✨ Custom destination
              </span>
              <h2 className="font-heading text-2xl font-extrabold text-ink">
                Can&apos;t find your destination?
              </h2>
              <p className="text-sm font-medium text-ink/80">
                Type any country, island, ancient empire, or fantasy kingdom —
                Madagascar, Atlantis, you name it.
              </p>
            </div>
            <form
              onSubmit={handleCustomSubmit}
              className="flex w-full flex-col gap-2.5 sm:flex-row lg:w-auto lg:min-w-[22rem]"
            >
              <Input
                value={customDestination}
                onChange={(e) => setCustomDestination(e.target.value)}
                placeholder="e.g. Iceland, Bhutan, Atlantis..."
                className="flex-1 bg-white"
                required
              />
              <Button
                type="submit"
                disabled={launching || !customDestination.trim()}
              >
                {launching ? "Launching…" : "Go"}
                <Rocket className="size-4" />
              </Button>
            </form>
          </div>
        </section>
      </main>

      <footer className="w-full border-t-2 border-ink bg-white">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-4 py-4 text-xs font-bold text-muted-foreground sm:flex-row sm:px-6">
          <span className="flex items-center gap-1.5">
            <Compass className="size-3.5" /> No login required — stored locally
            in your browser
          </span>
          <span>No quizzes. No grading. Just curiosity.</span>
        </div>
      </footer>
    </div>
  );
}
