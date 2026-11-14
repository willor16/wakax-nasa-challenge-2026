<template>
  <ShellHudWindow
    class="flex-1"
    title="Capture · Auscultation Audio"
    subtitle="Verify ambient noise below 55 dBA and record 30-second anatomical sample"
    icon="mic"
    tag-text="DATA CAPTURE"
  >
    <div class="flex flex-wrap gap-2 mb-4">
      <NuxtLink to="/capture/auscultation" class="px-4 h-9 rounded-[4px] menu-item-active text-[11.5px] font-bold flex items-center text-cabin-text">
        Auscultation Audio
      </NuxtLink>
      <NuxtLink to="/capture/physical" class="px-4 h-9 rounded-[4px] bg-cabin-inset border border-cabin-card/60 text-[11.5px] font-semibold flex items-center text-cabin-muted hover:text-cabin-text">
        Physical & Labs
      </NuxtLink>
      <NuxtLink to="/capture/vision" class="px-4 h-9 rounded-[4px] bg-cabin-inset border border-cabin-card/60 text-[11.5px] font-semibold flex items-center text-cabin-muted hover:text-cabin-text">
        Vision & Ocular
      </NuxtLink>
      <NuxtLink to="/capture/psych-sleep" class="px-4 h-9 rounded-[4px] bg-cabin-inset border border-cabin-card/60 text-[11.5px] font-semibold flex items-center text-cabin-muted hover:text-cabin-text">
        Psych, Motor & Sleep
      </NuxtLink>
    </div>
    <p class="text-[12px] text-cabin-muted">
      30-second cardiac and pulmonary acoustic recorder slot (D2-06).
    </p>
  </ShellHudWindow>
</template>
