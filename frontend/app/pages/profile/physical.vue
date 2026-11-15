<template>
  <ShellHudWindow
    class="flex-1"
    title="Physical & Clinical Profile"
    subtitle="Read-only vitals, live waveform, and point-of-care results"
    icon="capture"
    tag-text="READ ONLY"
  >
    <div class="flex gap-2 mb-4">
      <NuxtLink to="/profile/personal" class="px-4 h-9 rounded-[4px] bg-cabin-inset border border-cabin-card/60 text-[11.5px] font-semibold flex items-center text-cabin-muted hover:text-cabin-text">
        Personal Data
      </NuxtLink>
      <NuxtLink to="/profile/psychological" class="px-4 h-9 rounded-[4px] bg-cabin-inset border border-cabin-card/60 text-[11.5px] font-semibold flex items-center text-cabin-muted hover:text-cabin-text">
        Psychological
      </NuxtLink>
      <NuxtLink to="/profile/physical" class="px-4 h-9 rounded-[4px] menu-item-active text-[11.5px] font-bold flex items-center text-cabin-text">
        Physical & Clinical
      </NuxtLink>
    </div>
    <p class="text-[12px] text-cabin-muted">
      Clinical bars, live ECG waveform, and laboratory values slot (D2-03).
    </p>
  </ShellHudWindow>
</template>
