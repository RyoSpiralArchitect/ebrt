type IconProps = {
  name:
    | "lock"
    | "runs"
    | "chevron"
    | "check"
    | "close"
    | "minus"
    | "play"
    | "arrow"
    | "document";
  size?: number;
};

export function Icon({ name, size = 18 }: IconProps) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };

  if (name === "lock") {
    return (
      <svg {...common}>
        <rect x="5" y="10" width="14" height="11" rx="2" />
        <path d="M8.5 10V7a3.5 3.5 0 0 1 7 0v3" />
      </svg>
    );
  }
  if (name === "runs") {
    return (
      <svg {...common}>
        <path d="M8 6h12M8 12h12M8 18h12" />
        <circle cx="4" cy="6" r="1" fill="currentColor" stroke="none" />
        <circle cx="4" cy="12" r="1" fill="currentColor" stroke="none" />
        <circle cx="4" cy="18" r="1" fill="currentColor" stroke="none" />
      </svg>
    );
  }
  if (name === "chevron") {
    return (
      <svg {...common}>
        <path d="m9 6 6 6-6 6" />
      </svg>
    );
  }
  if (name === "check") {
    return (
      <svg {...common}>
        <path d="m6.5 12.5 3.2 3.2 7.8-8" />
      </svg>
    );
  }
  if (name === "close") {
    return (
      <svg {...common}>
        <path d="m7 7 10 10M17 7 7 17" />
      </svg>
    );
  }
  if (name === "play") {
    return (
      <svg {...common}>
        <path d="m8 5 11 7-11 7Z" />
      </svg>
    );
  }
  if (name === "arrow") {
    return (
      <svg {...common}>
        <path d="M5 12h14M14 7l5 5-5 5" />
      </svg>
    );
  }
  if (name === "document") {
    return (
      <svg {...common}>
        <path d="M6 3h8l4 4v14H6Z" />
        <path d="M14 3v5h4M9 12h6M9 16h6" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <path d="M7 12h10" />
    </svg>
  );
}
