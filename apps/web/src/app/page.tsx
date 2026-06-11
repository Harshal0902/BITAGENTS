import { Wordmark } from "@/components/AppShell";
import {
  Activity,
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  Cpu,
  GitBranch,
  Layers3,
  LineChart,
  LockKeyhole,
  RadioTower,
  ScrollText,
  Sparkles,
  TerminalSquare,
  WalletCards,
  Zap
} from "lucide-react";
import Link from "next/link";

const terminalLines = [
  "> bitagents run wallet-watcher",
  "> provider: online",
  "> compute: assigned",
  "> task: monitoring wallet activity",
  "> status: ready"
];

const agentCards = [
  {
    icon: WalletCards,
    title: "Wallet Monitoring",
    text: "Track wallets, balances, token activity, and on-chain movement."
  },
  {
    icon: ScrollText,
    title: "Research Agents",
    text: "Generate structured research summaries from market and project data."
  },
  {
    icon: GitBranch,
    title: "On-Chain Automation",
    text: "Create workflows that can alert, prepare, and eventually execute actions."
  },
  {
    icon: Cpu,
    title: "Decentralized Compute",
    text: "Allow compute providers to power agent tasks and earn from the network."
  }
];

const steps = [
  ["01", "Users request agent tasks", "Choose an agent, define the task, and submit it."],
  ["02", "Compute providers run the work", "Tasks are assigned to available compute providers that execute the workload."],
  ["03", "Results return on-chain-ready", "Users receive structured outputs while payments and settlement are handled through Solana."]
];

const computeFeatures = [
  "Agent runtime",
  "Task execution",
  "Research processing",
  "Wallet monitoring",
  "Future inference marketplace"
];

const utilityCards = [
  {
    title: "Platform Fees & Buybacks",
    text: "A portion of future platform fees is planned to support buybacks."
  },
  {
    title: "Compute Provider Staking",
    text: "Providers may stake BIT Agents to participate, build reputation, and reduce spam."
  },
  {
    title: "Premium Agent Access",
    text: "Token holders may receive access to advanced agents, higher limits, and premium workflows."
  },
  {
    title: "Marketplace Settlement",
    text: "Future versions may use BIT Agents across agent and compute marketplace flows."
  }
];

const roadmap = [
  {
    phase: "Phase 1",
    title: "Launch",
    items: ["BIT Agents token launch", "Holder airdrop", "Brand and marketplace setup"]
  },
  {
    phase: "Phase 2",
    title: "MVP",
    items: ["Wallet Watcher Agent", "Research Agent", "Compute Provider Worker", "Solana devnet task payments"]
  },
  {
    phase: "Phase 3",
    title: "Marketplace",
    items: ["Agent task marketplace", "Provider dashboard", "Task assignment", "Compute rewards"]
  },
  {
    phase: "Phase 4",
    title: "Network",
    items: ["More agents", "Token utility integrations", "Provider staking", "Inference marketplace experiments"]
  }
];

export default function HomePage() {
  return (
    <div className="marketing-page overflow-hidden">
      <section className="relative mx-auto grid min-h-[calc(100vh-73px)] max-w-7xl items-center gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1.02fr_0.98fr] lg:px-8 lg:py-14">
        <div className="relative z-10 max-w-3xl">
          <div className="mb-7">
            <Wordmark />
          </div>
          <div className="inline-flex items-center gap-2 rounded-md border border-ember/30 bg-ember/10 px-3 py-2 font-mono text-xs font-black uppercase text-coral">
            <Sparkles size={14} /> AI agent marketplace
          </div>
          <h1 className="mt-7 max-w-3xl text-5xl font-black leading-[1.02] text-[#221912] sm:text-6xl lg:text-7xl">
            AI agents powered by decentralized compute.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-[#5d5147] sm:text-xl">
            BIT Agents lets users run specialized agents for wallet monitoring, research, automation, and on-chain workflows — powered by a decentralized compute network.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link href="/coming-soon" className="inline-flex items-center justify-center gap-2 rounded-md bg-[#d76545] px-5 py-3 font-black text-[#fff8ef] transition hover:bg-[#bd5134]">
              Launch App <ArrowRight size={18} />
            </Link>
            <Link href="#roadmap" className="inline-flex items-center justify-center gap-2 rounded-md border border-[#d8cabb] bg-[#fff9f0] px-5 py-3 font-black text-[#2b2118] transition hover:border-[#d76545] hover:text-[#bd5134]">
              Read Roadmap <LineChart size={18} />
            </Link>
          </div>
        </div>

        <div className="relative z-10">
          <div className="rounded-md border border-[#dacdbc] bg-[#fff9f0] p-4 shadow-[0_20px_70px_rgba(90,55,32,0.12)]">
            <div className="flex items-center justify-between border-b border-[#e0d3c4] pb-4">
              <div className="flex items-center gap-3">
                <TerminalSquare className="text-ember" size={22} />
                <div>
                  <p className="font-mono text-sm font-black text-[#241a12]">agent-task.term</p>
                  <p className="font-mono text-xs text-[#8a7a6d]">runtime / provider assigned</p>
                </div>
              </div>
              <div className="flex gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-ember" />
                <span className="h-2.5 w-2.5 rounded-full bg-coral" />
                <span className="h-2.5 w-2.5 rounded-full bg-slate-500" />
              </div>
            </div>
            <div className="space-y-4 py-5 font-mono text-sm leading-7 text-[#3b3027] sm:text-base">
              {terminalLines.map((line, index) => (
                <p key={line} className={index === 4 ? "text-mint" : "text-[#3b3027]"}>{line}</p>
              ))}
            </div>
            <div className="grid gap-3 border-t border-[#e0d3c4] pt-4 sm:grid-cols-3">
              <Metric label="latency" value="42ms" />
              <Metric label="queue" value="ready" />
              <Metric label="settle" value="solana" />
            </div>
          </div>
        </div>
      </section>

      <Section id="product" eyebrow="Product" title="From prompts to autonomous workflows.">
        <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
          <p className="text-lg leading-8 text-[#5d5147]">
            BIT Agents turns everyday crypto workflows into agent-powered systems. Users can monitor wallets, research markets, automate repetitive tasks, and coordinate compute-backed execution from one marketplace.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            {agentCards.map(({ icon: Icon, title, text }) => (
              <Card key={title} icon={<Icon size={22} />} title={title} text={text} />
            ))}
          </div>
        </div>
      </Section>

      <Section eyebrow="Flow" title="How it works">
        <div className="grid gap-4 lg:grid-cols-3">
          {steps.map(([number, title, text]) => (
            <div key={number} className="rounded-md border border-[#ded2c3] bg-[#fff9f0] p-5 transition hover:border-ember/70 hover:bg-[#fff4e6]">
              <p className="font-mono text-sm font-black text-ember">{number}</p>
              <h3 className="mt-5 text-xl font-black text-[#241a12]">{title}</h3>
              <p className="mt-3 leading-7 text-[#6e6258]">{text}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section id="compute" eyebrow="Compute" title="Agents do not just think. They run.">
        <div className="grid gap-8 lg:grid-cols-[1fr_0.85fr]">
          <div className="rounded-md border border-[#e0d3c4] bg-[#f5efe6] p-6">
            <p className="max-w-3xl text-lg leading-8 text-[#5d5147]">
              Useful agents need compute to monitor markets, process data, run research, and execute workflows. BIT Agents connects demand for agent tasks with supply from compute providers.
            </p>
            <div className="mt-7 grid gap-3 sm:grid-cols-2">
              {computeFeatures.map((feature) => (
                <div key={feature} className="flex items-center gap-3 rounded-md border border-[#ded2c3] bg-[#fff9f0] p-4 font-bold text-[#3b3027]">
                  <Zap size={18} className="text-ember" /> {feature}
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-md border border-ember/30 bg-ember/10 p-6">
            <RadioTower className="text-coral" size={28} />
            <h3 className="mt-5 text-2xl font-black text-[#241a12]">Compute supply for agent demand.</h3>
            <p className="mt-4 leading-7 text-[#5d5147]">
              Providers run workloads, return structured outputs, and help form the execution layer for marketplace agents.
            </p>
          </div>
        </div>
      </Section>

      <Section id="token-utility" eyebrow="Token Utility" title="Designed around real platform usage.">
        <p className="max-w-3xl text-lg leading-8 text-[#5d5147]">
          The BIT Agents token is designed to connect product usage with marketplace access, compute participation, and future settlement flows.
        </p>
        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {utilityCards.map((card) => (
            <Card key={card.title} icon={<LockKeyhole size={22} />} title={card.title} text={card.text} />
          ))}
        </div>
      </Section>

      <Section id="roadmap" eyebrow="Timeline" title="Roadmap">
        <div className="grid gap-4 lg:grid-cols-4">
          {roadmap.map((phase) => (
            <div key={phase.phase} className="rounded-md border border-[#ded2c3] bg-[#fff9f0] p-5">
              <p className="font-mono text-sm font-black uppercase text-ember">{phase.phase}</p>
              <h3 className="mt-3 text-2xl font-black text-[#241a12]">{phase.title}</h3>
              <ul className="mt-5 space-y-3">
                {phase.items.map((item) => (
                  <li key={item} className="flex gap-3 text-sm leading-6 text-[#5d5147]">
                    <CheckCircle2 className="mt-0.5 shrink-0 text-coral" size={16} /> {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Section>

      <Section eyebrow="Platform" title="Built for agent-native workflows.">
        <div className="grid gap-8 lg:grid-cols-[0.95fr_1.05fr]">
          <p className="text-lg leading-8 text-[#5d5147]">
            BIT Agents is focused on active automation: agents that watch, research, alert, prepare, and coordinate workflows across on-chain activity and off-chain compute.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <Compare title="Manual crypto workflows" icon={<Layers3 size={22} />} items={["Manual wallet checks", "Fragmented research", "Repeated operational tasks"]} />
            <Compare title="BIT Agents" icon={<BrainCircuit size={22} />} items={["Active automation", "AI agents", "Compute-powered workflows"]} accent />
          </div>
        </div>
      </Section>

      <footer className="border-t border-[#e0d3c4] bg-[#efe4d6] px-4 py-10 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-7xl gap-8 md:grid-cols-[1fr_auto] md:items-end">
          <div>
            <Wordmark compact />
            <p className="mt-4 max-w-md font-mono text-sm text-[#6e6258]">AI Agents. On-chain. Decentralized compute.</p>
          </div>
          <div className="flex flex-wrap gap-3 font-bold text-[#5d5147]">
            <Link className="hover:text-coral" href="https://x.com/" target="_blank">X</Link>
            <Link className="hover:text-coral" href="https://telegram.org/" target="_blank">Telegram</Link>
          </div>
          <p className="font-mono text-xs text-[#8a7a6d] md:col-span-2">Copyright 2026 BIT Agents. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}

function Section({ id, eyebrow, title, children }: { id?: string; eyebrow: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="mx-auto max-w-7xl scroll-mt-28 px-4 py-16 sm:px-6 lg:px-8 lg:py-20">
      <p className="font-mono text-sm font-black uppercase text-ember">{eyebrow}</p>
      <h2 className="mt-3 max-w-4xl text-3xl font-black leading-tight text-[#241a12] sm:text-5xl">{title}</h2>
      <div className="mt-9">{children}</div>
    </section>
  );
}

function Card({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return (
    <div className="rounded-md border border-[#ded2c3] bg-[#fff9f0] p-5 transition hover:border-ember/70 hover:bg-[#fff4e6]">
      <div className="text-ember">{icon}</div>
      <h3 className="mt-4 text-lg font-black text-[#241a12]">{title}</h3>
      <p className="mt-3 leading-7 text-[#6e6258]">{text}</p>
    </div>
  );
}

function Compare({ title, icon, items, accent = false }: { title: string; icon: React.ReactNode; items: string[]; accent?: boolean }) {
  return (
    <div className={`rounded-md border p-5 ${accent ? "border-ember/40 bg-ember/10" : "border-[#ded2c3] bg-[#fff9f0]"}`}>
      <div className={accent ? "text-coral" : "text-[#5d5147]"}>{icon}</div>
      <h3 className="mt-4 text-xl font-black text-[#241a12]">{title}</h3>
      <ul className="mt-5 space-y-3">
        {items.map((item) => (
          <li key={item} className="flex items-center gap-3 text-[#5d5147]">
            <Activity size={15} className="text-ember" /> {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[#e0d3c4] bg-[#f5efe6] p-3">
      <p className="font-mono text-[11px] uppercase text-[#8a7a6d]">{label}</p>
      <p className="mt-1 font-mono text-sm font-black text-[#241a12]">{value}</p>
    </div>
  );
}
