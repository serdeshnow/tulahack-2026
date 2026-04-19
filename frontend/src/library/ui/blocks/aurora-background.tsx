"use client";

import React, { type ReactNode } from "react";

import { cn } from "@/library/utils";

interface AuroraBackgroundProps extends React.HTMLProps<HTMLDivElement> {
  children: ReactNode;
  showRadialGradient?: boolean;
}

export const AuroraBackground = ({
  className,
  children,
  showRadialGradient = true,
  ...props
}: AuroraBackgroundProps) => {
  return (
    <main className="min-h-screen bg-background">
      <div
        className={cn(
          "relative flex min-h-screen items-center overflow-hidden bg-background text-foreground",
          className
        )}
        {...props}
      >
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div
            className={cn(
              "absolute inset-[-12%] opacity-100 blur-2xl",
              "[background-image:repeating-linear-gradient(100deg,rgba(255,255,255,0.82)_0%,rgba(255,255,255,0.82)_7%,rgba(255,255,255,0)_10%,rgba(255,255,255,0)_12%,rgba(255,255,255,0.82)_16%),repeating-linear-gradient(100deg,rgba(37,99,235,0.34)_10%,rgba(165,180,252,0.34)_15%,rgba(125,211,252,0.3)_20%,rgba(196,181,253,0.3)_25%,rgba(59,130,246,0.34)_30%)]",
              "[background-size:300%_300%,200%_200%]",
              "[background-position:50%_50%,50%_50%]",
              "[filter:blur(16px)] [animation:aurora_24s_ease-in-out_infinite_alternate]",
              "after:absolute after:inset-0 after:content-['']",
              "after:[background-image:repeating-linear-gradient(100deg,rgba(255,255,255,0.54)_0%,rgba(255,255,255,0.54)_7%,rgba(255,255,255,0)_10%,rgba(255,255,255,0)_12%,rgba(255,255,255,0.54)_16%),repeating-linear-gradient(100deg,rgba(37,99,235,0.26)_10%,rgba(129,140,248,0.28)_15%,rgba(125,211,252,0.24)_20%,rgba(191,219,254,0.3)_25%,rgba(59,130,246,0.26)_30%)]",
              "after:[background-size:220%_220%,140%_140%]",
              "after:[background-position:50%_50%,50%_50%]",
              "after:[animation:aurora_18s_ease-in-out_infinite_reverse] after:mix-blend-multiply",
              showRadialGradient &&
                "[mask-image:radial-gradient(ellipse_at_35%_30%,black_18%,transparent_78%)]"
            )}
          />
          <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(248,248,248,0.28)_0%,rgba(248,248,248,0.56)_44%,rgba(248,248,248,0.74)_100%)]" />
        </div>

        <div className="relative z-10 w-full">{children}</div>
      </div>
    </main>
  );
};
