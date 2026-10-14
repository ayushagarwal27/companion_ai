import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Slot } from "radix-ui"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg border-2 border-ink font-sans text-sm font-bold whitespace-nowrap transition-all duration-150 outline-none select-none disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "bg-sunshine text-ink shadow-[3px_3px_0px_var(--ink)] hover:bg-sunshine-dim hover:shadow-[4px_4px_0px_var(--ink)] hover:-translate-x-px hover:-translate-y-px active:translate-x-[2px] active:translate-y-[2px] active:shadow-[1px_1px_0px_var(--ink)]",
        secondary:
          "bg-white text-ink shadow-[3px_3px_0px_var(--ink)] hover:bg-cyan-soft hover:shadow-[4px_4px_0px_var(--ink)] hover:-translate-x-px hover:-translate-y-px active:translate-x-[2px] active:translate-y-[2px] active:shadow-[1px_1px_0px_var(--ink)]",
        outline:
          "border-ink bg-transparent text-ink shadow-[2px_2px_0px_var(--ink)] hover:bg-muted active:translate-x-[1px] active:translate-y-[1px] active:shadow-none",
        ghost:
          "border-transparent text-ink hover:bg-muted active:translate-y-px",
        destructive:
          "bg-bubblegum text-ink shadow-[3px_3px_0px_var(--ink)] hover:shadow-[4px_4px_0px_var(--ink)] hover:-translate-x-px hover:-translate-y-px active:translate-x-[2px] active:translate-y-[2px] active:shadow-[1px_1px_0px_var(--ink)]",
        link: "border-transparent text-ink underline underline-offset-4 hover:text-ink/70",
      },
      size: {
        default: "h-10 px-4 has-data-[icon=inline-end]:pr-3 has-data-[icon=inline-start]:pl-3",
        sm: "h-8 gap-1 rounded-md px-2.5 text-xs",
        lg: "h-12 px-6 text-base",
        icon: "size-10",
        "icon-sm": "size-8 rounded-md",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
