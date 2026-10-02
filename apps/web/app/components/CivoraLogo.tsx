import Image from "next/image";

type CivoraMarkProps = {
  className?: string;
  priority?: boolean;
  decorative?: boolean;
};

export function CivoraMark({
  className = "h-8 w-8",
  priority = false,
  decorative = false,
}: CivoraMarkProps) {
  return (
    <Image
      src="/brand/civora-primary-mark.png"
      alt={decorative ? "" : "Civora"}
      width={1254}
      height={1254}
      priority={priority}
      className={`shrink-0 object-contain ${className}`}
    />
  );
}

type CivoraLogoProps = {
  className?: string;
  markClassName?: string;
  wordmarkClassName?: string;
  priority?: boolean;
};

export default function CivoraLogo({
  className = "",
  markClassName = "h-8 w-8",
  wordmarkClassName = "text-[17px] font-semibold tracking-[-0.02em] text-slate-950",
  priority = false,
}: CivoraLogoProps) {
  return (
    <span role="img" className={`inline-flex items-center gap-2.5 ${className}`} aria-label="Civora">
      <CivoraMark className={markClassName} priority={priority} decorative />
      <span aria-hidden="true" className={wordmarkClassName}>
        Civora
      </span>
    </span>
  );
}
