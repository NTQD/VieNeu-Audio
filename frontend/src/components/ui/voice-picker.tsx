"use client"

// Adapted tu ElevenLabs UI (github.com/elevenlabs/ui, MIT) - 2026-09-12.
// 2 thay doi so voi ban goc: (1) khong dung type "ElevenLabs.Voice" tu SDK
// @elevenlabs/elevenlabs-js (chi la KIEU DU LIEU, khong goi API that nao ca -
// thay bang kieu Voice noi bo, khop voi data/voice_presets.json cua chinh
// VoxDirector, xem frontend/src/lib/types.ts); (2) thay <Orb> (can toan bo
// @react-three/fiber + three - qua nang cho 1 avatar nho) bang VoiceAvatar
// (CSS thuan, cung mo-tip voi logo).

import * as React from "react"
import { Check, ChevronsUpDown, Pause, Play } from "lucide-react"

import { cn } from "@/lib/utils"
import { AudioPlayerProvider, useAudioPlayer } from "@/components/ui/audio-player"
import { Button } from "@/components/ui/button"
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import VoiceAvatar from "@/components/ui/voice-avatar"

export interface Voice {
  voiceId: string
  name: string
  previewUrl?: string
  labels?: {
    accent?: string
    gender?: string
    age?: string
    description?: string
  }
}

interface VoicePickerProps {
  voices: Voice[]
  value?: string
  onValueChange?: (value: string) => void
  placeholder?: string
  className?: string
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

function VoicePicker({
  voices,
  value,
  onValueChange,
  placeholder = "Chọn giọng đọc...",
  className,
  open,
  onOpenChange,
}: VoicePickerProps) {
  const [internalOpen, setInternalOpen] = React.useState(false)
  const isControlled = open !== undefined
  const isOpen = isControlled ? open : internalOpen
  const setIsOpen = isControlled ? onOpenChange : setInternalOpen

  const selectedVoice = voices.find((v) => v.voiceId === value)

  return (
    <AudioPlayerProvider>
      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger
          render={
            <Button
              variant="outline"
              role="combobox"
              aria-expanded={isOpen}
              className={cn("w-full justify-between", className)}
            />
          }
        >
          {selectedVoice ? (
            <div className="flex items-center gap-2 overflow-hidden">
              <VoiceAvatar className="size-6" />
              <span className="truncate">{selectedVoice.name}</span>
            </div>
          ) : (
            <span className="text-muted-foreground">{placeholder}</span>
          )}
          <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
        </PopoverTrigger>
        <PopoverContent className="w-[340px] p-0">
          <Command>
            <CommandInput placeholder="Tìm giọng theo tên, vùng miền, giới tính..." />
            <CommandList>
              <CommandEmpty>Không tìm thấy giọng nào.</CommandEmpty>
              <CommandGroup>
                {voices.map((voice) => (
                  <VoicePickerItem
                    key={voice.voiceId}
                    voice={voice}
                    isSelected={value === voice.voiceId}
                    onSelect={() => {
                      onValueChange?.(voice.voiceId)
                      setIsOpen?.(false)
                    }}
                  />
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </AudioPlayerProvider>
  )
}

interface VoicePickerItemProps {
  voice: Voice
  isSelected: boolean
  onSelect: () => void
}

function VoicePickerItem({ voice, isSelected, onSelect }: VoicePickerItemProps) {
  const [isHovered, setIsHovered] = React.useState(false)
  const player = useAudioPlayer()

  const preview = voice.previewUrl
  const audioItem = React.useMemo(
    () => (preview ? { id: voice.voiceId, src: preview, data: voice } : null),
    [preview, voice]
  )

  const isPlaying = Boolean(audioItem) && player.isItemActive(audioItem!.id) && player.isPlaying

  // "Voice Audition" (2026-09-12, yeu cau nguoi dung): di chuot QUA CA DONG
  // (khong chi bam vao avatar) la TU DONG doc mau, roi chuot RA la dung ngay
  // ("move the mouse to finish") - khac voi hanh vi cu (phai bam moi phat).
  const handleMouseEnter = React.useCallback(() => {
    setIsHovered(true)
    if (audioItem) player.play(audioItem)
  }, [audioItem, player])

  const handleMouseLeave = React.useCallback(() => {
    setIsHovered(false)
    if (audioItem && player.isItemActive(audioItem.id)) player.pause()
  }, [audioItem, player])

  return (
    <CommandItem
      value={voice.voiceId}
      keywords={[
        voice.name,
        voice.labels?.accent,
        voice.labels?.gender,
        voice.labels?.age,
        voice.labels?.description,
      ].filter((k): k is string => Boolean(k))}
      onSelect={onSelect}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className="flex items-center gap-3"
    >
      <div className="relative z-10 size-8 shrink-0">
        <VoiceAvatar talking={isPlaying} className="absolute inset-0" />
        {preview && isHovered && (
          <div className="pointer-events-none absolute inset-0 flex size-8 shrink-0 items-center justify-center rounded-full bg-black/40 backdrop-blur-sm">
            {isPlaying ? (
              <Pause className="size-3 text-white" />
            ) : (
              <Play className="size-3 text-white" />
            )}
          </div>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-0.5">
        <span className="font-medium">{voice.name}</span>
        {voice.labels && (
          <div className="text-muted-foreground flex items-center gap-1.5 text-xs">
            {voice.labels.accent && <span>{voice.labels.accent}</span>}
            {voice.labels.gender && <span>•</span>}
            {voice.labels.gender && <span>{voice.labels.gender}</span>}
            {voice.labels.age && <span>•</span>}
            {voice.labels.age && <span className="capitalize">{voice.labels.age}</span>}
            {voice.labels.description && <span>•</span>}
            {voice.labels.description && <span>{voice.labels.description}</span>}
          </div>
        )}
      </div>

      <Check className={cn("ml-auto size-4 shrink-0", isSelected ? "opacity-100" : "opacity-0")} />
    </CommandItem>
  )
}

export { VoicePicker, VoicePickerItem }
