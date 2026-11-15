<script setup lang="ts">
import type { StatusTone } from '~/utils/profileCharts'

const props = withDefaults(
  defineProps<{
    coreTempDisplay: string
    hydrationDisplay: string
    cardiacTone?: StatusTone
    pulmonaryTone?: StatusTone
    ocularTone?: StatusTone
  }>(),
  {
    cardiacTone: 'nominal',
    pulmonaryTone: 'nominal',
    ocularTone: 'nominal',
  },
)

function organStrokeVar(tone: StatusTone): string {
  if (tone === 'critical') return 'var(--color-status-critical)'
  if (tone === 'warn') return 'var(--color-rem-accent)'
  return 'var(--color-status-ok)'
}

const ocularStroke = computed(() => organStrokeVar(props.ocularTone))
const pulmonaryStroke = computed(() => organStrokeVar(props.pulmonaryTone))
const cardiacStroke = computed(() => organStrokeVar(props.cardiacTone))
</script>

<template>
  <div class="h-full flex flex-col justify-between gap-4">
    <div class="relative flex-1 min-h-[350px] flex items-center justify-center hologram-scanline overflow-hidden rounded-[4px] bg-cabin-inset/45 border border-cabin-card/45">
      <svg
        viewBox="0 0 360 360"
        class="w-full max-w-[332px] h-auto hologram-shell select-none"
        role="img"
        aria-label="Astronaut anatomical biometric scan"
      >
        <circle
          cx="180"
          cy="180"
          r="158"
          fill="none"
          stroke="rgba(255, 236, 209, 0.18)"
          stroke-width="1"
        />
        <circle
          cx="180"
          cy="180"
          r="122"
          fill="none"
          stroke="var(--color-surface-card)"
          stroke-width="1.15"
          stroke-dasharray="6 6"
        />
        <line x1="180" y1="14" x2="180" y2="346" stroke="rgba(21, 97, 109, 0.32)" stroke-width="1" />
        <line x1="14" y1="180" x2="346" y2="180" stroke="rgba(21, 97, 109, 0.32)" stroke-width="1" />

        <g fill="rgba(4, 30, 46, 0.55)" stroke="var(--color-status-ok)" stroke-width="1.5" stroke-linejoin="round">
          <ellipse cx="180" cy="64" rx="22" ry="26" />
          <path d="M162 60 C168 52, 192 52, 198 60 C196 69, 164 69, 162 60 Z" fill="rgba(42, 239, 75, 0.12)" />
          <path d="M172 90 L188 90 L191 102 L169 102 Z" />
          <path
            d="M140 106 C154 99, 206 99, 220 106 L236 154 L225 196 L213 194 L218 154 L206 126 L204 198 L156 198 L154 126 L142 154 L147 194 L135 196 L124 154 Z"
          />
          <path d="M156 198 L204 198 L210 226 L195 316 L182 316 L180 240 L178 316 L165 316 L150 226 Z" />
        </g>

        <line
          x1="180"
          y1="92"
          x2="180"
          y2="212"
          stroke="rgba(255, 236, 209, 0.36)"
          stroke-width="1.2"
          stroke-dasharray="3 3"
        />

        <g fill="rgba(41, 148, 166, 0.16)" :stroke="pulmonaryStroke" stroke-width="1.35">
          <path d="M175 118 C163 118, 158 132, 159 152 C160 162, 171 162, 176 154 Z" />
          <path d="M185 118 C197 118, 202 132, 201 152 C200 162, 189 162, 184 154 Z" />
        </g>

        <g>
          <path
            d="M183 136 C180 131, 173 133, 174 140 C175 146, 183 151, 183 151 C183 151, 191 146, 192 140 C193 133, 186 131, 183 136 Z"
            fill="rgba(42, 239, 75, 0.25)"
            :stroke="cardiacStroke"
            stroke-width="1.5"
          />
          <circle cx="183" cy="142" r="11" fill="none" :stroke="cardiacStroke" stroke-width="0.9" opacity="0.65" />
        </g>

        <g>
          <circle cx="172" cy="60" r="3" :fill="ocularStroke" />
          <circle cx="188" cy="60" r="3" :fill="ocularStroke" />
          <line x1="194" y1="58" x2="250" y2="44" :stroke="ocularStroke" stroke-width="1" />
          <circle cx="250" cy="44" r="2.5" :fill="ocularStroke" />
          <text
            x="256"
            y="47"
            fill="var(--color-text-primary)"
            font-size="9"
            font-family="JetBrains Mono, monospace"
            font-weight="700"
          >
            OCULAR
          </text>
        </g>

        <g>
          <line x1="158" y1="138" x2="98" y2="124" :stroke="pulmonaryStroke" stroke-width="1" />
          <circle cx="98" cy="124" r="2.5" :fill="pulmonaryStroke" />
          <text
            x="44"
            y="127"
            fill="var(--color-text-primary)"
            font-size="9"
            font-family="JetBrains Mono, monospace"
            font-weight="700"
          >
            THORAX
          </text>
        </g>

        <g>
          <line x1="194" y1="143" x2="254" y2="156" :stroke="cardiacStroke" stroke-width="1" />
          <circle cx="254" cy="156" r="2.5" :fill="cardiacStroke" />
          <text
            x="260"
            y="159"
            fill="var(--color-text-primary)"
            font-size="9"
            font-family="JetBrains Mono, monospace"
            font-weight="700"
          >
            CARDIAC
          </text>
        </g>
      </svg>
    </div>

    <div class="grid grid-cols-2 gap-3">
      <div class="rounded-[4px] bg-cabin-inset border border-cabin-card/65 px-4 py-3 flex flex-col justify-between min-h-[72px]">
        <span class="text-[10px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
          CORE TEMP
        </span>
        <span class="font-mono text-[20px] font-bold text-cabin-text leading-tight">
          {{ coreTempDisplay }}
        </span>
      </div>

      <div class="rounded-[4px] bg-cabin-inset border border-cabin-card/65 px-4 py-3 flex flex-col justify-between min-h-[72px]">
        <span class="text-[10px] font-bold tracking-[0.06em] uppercase text-cabin-muted">
          HYDRATION
        </span>
        <span class="font-mono text-[20px] font-bold text-cabin-text leading-tight">
          {{ hydrationDisplay }}
        </span>
      </div>
    </div>
  </div>
</template>
