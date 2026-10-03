import { useEffect, useRef, useState } from "react";

export { CountUp };

/**
 * Animates a figure from a starting value to its target the first time it
 * scrolls into view.
 *
 * Values reach the stat components as formatted strings ("₹1,234 Cr", "42%",
 * "—") as often as numbers, so a numeric core is parsed out and the surrounding
 * text is preserved. A value with no clean numeric core - a date, an em dash, a
 * label - is rendered untouched, which makes this safe to drop into any figure
 * slot without tracking which callers pass what.
 */

function parseValue(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    const decimals = Number.isInteger(value)
      ? 0
      : (String(value).split(".")[1] || "").length;
    return { target: value, prefix: "", suffix: "", decimals };
  }

  if (typeof value === "string") {
    const match = value.match(/^(\D*?)(-?\d[\d,]*(?:\.\d+)?)(\D*)$/);
    if (match) {
      const raw = match[2];
      const target = Number(raw.replace(/,/g, ""));
      if (Number.isFinite(target)) {
        const decimals = raw.includes(".") ? raw.split(".")[1].length : 0;
        return { target, prefix: match[1], suffix: match[3], decimals };
      }
    }
  }

  return null;
}

function formatNumber(n, decimals) {
  if (decimals > 0) {
    return n.toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  }
  return Math.round(n).toLocaleString();
}

function CountUp({ value, from = 0, duration = 900, className }) {
  const parsed = parseValue(value);
  const target = parsed ? parsed.target : null;
  const [display, setDisplay] = useState(() => (parsed ? from : value));
  const nodeRef = useRef(null);
  const frameRef = useRef(0);

  useEffect(() => {
    if (target === null) {
      setDisplay(value);
      return undefined;
    }

    const node = nodeRef.current;
    if (!node) return undefined;

    setDisplay(from);
    let cancelled = false;

    const animate = () => {
      const start = performance.now();
      const step = (now) => {
        if (cancelled) return;
        const progress = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - progress, 3);
        if (progress < 1) {
          setDisplay(from + (target - from) * eased);
          frameRef.current = requestAnimationFrame(step);
        } else {
          setDisplay(target);
        }
      };
      frameRef.current = requestAnimationFrame(step);
    };

    const reduceMotion =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        observer.disconnect();
        if (reduceMotion) setDisplay(target);
        else animate();
      },
      { threshold: 0.25 },
    );
    observer.observe(node);

    return () => {
      cancelled = true;
      observer.disconnect();
      cancelAnimationFrame(frameRef.current);
    };
  }, [target, from, duration, value]);

  const rendered =
    parsed && typeof display === "number"
      ? `${parsed.prefix}${formatNumber(display, parsed.decimals)}${parsed.suffix}`
      : display;

  return (
    <span ref={nodeRef} className={className}>
      {rendered}
    </span>
  );
}
