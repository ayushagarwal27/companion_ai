"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { COUNTRIES } from "@/lib/countries";

export default function Home() {
  const router = useRouter();
  const [country, setCountry] = useState<string>("");

  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-2xl">Companion AI</CardTitle>
          <CardDescription>
            Pick a country and start learning with a friendly AI guide — perfect
            for curious kids and young adults.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Select value={country} onValueChange={setCountry}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Choose a country" />
            </SelectTrigger>
            <SelectContent>
              {COUNTRIES.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Button
            disabled={!country}
            onClick={() =>
              router.push(
                `/chat?country=${encodeURIComponent(country)}&v=${crypto.randomUUID()}`
              )
            }
          >
            Start chatting
          </Button>
        </CardContent>
      </Card>
    </main>
  );
}
