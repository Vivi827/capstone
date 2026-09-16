import Image from "next/image";

import { cn } from "@/lib/utils";

type PallyCharacterProps = {
  className?: string;
  priority?: boolean;
};

export function PallyCharacter({ className, priority = false }: PallyCharacterProps) {
  return (
    <div className={cn("relative size-[308px]", className)}>
      <Image
        alt="Pally 캐릭터"
        className="object-contain"
        fill
        priority={priority}
        sizes="308px"
        src="/pally/pally-character.svg"
      />
    </div>
  );
}
