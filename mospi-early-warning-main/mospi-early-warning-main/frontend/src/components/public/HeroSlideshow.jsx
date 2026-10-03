import { useEffect, useMemo, useState } from "react";

/** Five infrastructure photographs, crossfaded behind the hero copy. */
export const HERO_IMAGES = [
  { src: "/images/hero/01.jpg", caption: "hero.caption01" },
  { src: "/images/hero/02.jpg", caption: "hero.caption02" },
  { src: "/images/hero/03.jpg", caption: "hero.caption03" },
  { src: "/images/hero/04.jpg", caption: "hero.caption04" },
  { src: "/images/hero/05.jpg", caption: "hero.caption05" },
];

/**
 * Background slideshow for the hero.
 *
 * Every image is mounted and crossfaded by opacity, so the next frame is
 * already decoded when it fades in. A navy gradient stays on top of the
 * photographs to keep the white hero copy readable in all light levels. The
 * cycle respects `prefers-reduced-motion` and the pips double as accessible
 * playhead controls.
 */
export function HeroSlideshow({ t, interval = 3000 }) {
  const [index, setIndex] = useState(0);

  const reduced = useMemo(
    () =>
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    [],
  );

  useEffect(() => {
    if (reduced) return undefined;
    const id = setInterval(() => setIndex((i) => (i + 1) % HERO_IMAGES.length), interval);
    return () => clearInterval(id);
  }, [reduced, interval]);

  const caption = t(HERO_IMAGES[index].caption);

  return (
    <>
      <div className="absolute inset-0 z-0" role="presentation">
        {HERO_IMAGES.map((img, i) => (
          <img
            key={img.src}
            src={img.src}
            alt=""
            aria-hidden="true"
            className={`absolute inset-0 h-full w-full object-cover transition-opacity ${
              reduced ? "duration-0" : "duration-[900ms] ease-out"
            } ${i === index ? "opacity-100" : "opacity-0"}`}
          />
        ))}
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              "linear-gradient(180deg, rgba(6,14,55,0.78) 0%, rgba(10,21,77,0.55) 55%, rgba(6,14,55,0.82) 100%)",
          }}
        />
      </div>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 flex items-end justify-between gap-4 px-6 pb-4">
        <p className="text-[10px] font-bold uppercase tracking-widest text-white/70">
          {caption}
        </p>
        <div className="flex items-center gap-2" role="group" aria-label={caption}>
          {HERO_IMAGES.map((img, i) => (
            <button
              key={img.src}
              type="button"
              onClick={() => setIndex(i)}
              aria-label={t(img.caption)}
              aria-current={i === index}
              className="group flex h-8 items-center justify-center"
            >
              <span
                className={`block h-2 rounded-full transition-all duration-300 ${
                  i === index
                    ? "w-6 bg-white"
                    : "w-2 bg-white/40 group-hover:bg-white/70"
                }`}
              />
            </button>
          ))}
        </div>
      </div>
    </>
  );
}