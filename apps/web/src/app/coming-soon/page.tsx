import { Wordmark } from "@/components/AppShell";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function ComingSoonPage() {
  return (
    <section className="marketing-page mx-auto grid min-h-[calc(100vh-73px)] max-w-3xl place-items-center px-4 py-16 sm:px-6 lg:px-8">
      <div className="w-full rounded-md border border-[#ded2c3] bg-[#fff9f0] p-6 text-center shadow-[0_20px_70px_rgba(90,55,32,0.12)] sm:p-10">
        <div className="flex justify-center">
          <Wordmark />
        </div>
        <h1 className="mt-8 text-3xl font-black text-[#241a12] sm:text-5xl">The BIT Agents app is coming soon.</h1>
        <p className="mx-auto mt-5 max-w-xl text-lg leading-8 text-[#5d5147]">
          We are currently building the first version of the AI Agent Marketplace.
        </p>
        <Link href="/" className="mt-8 inline-flex items-center justify-center gap-2 rounded-md bg-[#d76545] px-5 py-3 font-black text-[#fff8ef] transition hover:bg-[#bd5134]">
          <ArrowLeft size={18} /> Back
        </Link>
      </div>
    </section>
  );
}
