import * as React from 'react'
import * as PopoverPrimitive from '@radix-ui/react-popover'

import { cn } from '@/library/utils'

function Combobox({ ...props }: React.ComponentProps<typeof PopoverPrimitive.Root>) {
  return <PopoverPrimitive.Root data-slot='combobox' {...props} />
}

function ComboboxTrigger({ ...props }: React.ComponentProps<typeof PopoverPrimitive.Trigger>) {
  return <PopoverPrimitive.Trigger data-slot='combobox-trigger' {...props} />
}

function ComboboxContent({
  className,
  align = 'start',
  side = 'bottom',
  sideOffset = 4,
  disablePortal = false,
  ...props
}: React.ComponentProps<typeof PopoverPrimitive.Content> & {
  disablePortal?: boolean
}) {
  const content = (
    <PopoverPrimitive.Content
      data-slot='combobox-content'
      align={align}
      side={side}
      sideOffset={sideOffset}
      className={cn(
        'bg-popover text-popover-foreground data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 z-50 max-h-(--radix-popover-content-available-height) w-[--radix-popover-trigger-width] min-w-0 origin-(--radix-popover-content-transform-origin) overflow-hidden rounded-lg border shadow-md outline-none',
        className
      )}
      {...props}
    />
  )

  return disablePortal ? content : <PopoverPrimitive.Portal>{content}</PopoverPrimitive.Portal>
}

export { Combobox, ComboboxTrigger, ComboboxContent }
