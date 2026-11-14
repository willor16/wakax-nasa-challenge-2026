<template>
  <ShellHudWindow
    class="flex-1"
    title="Psychological & Cognitive Profile"
    subtitle="Read-only 14-day wellbeing trend and reaction performance"
    icon="profile"
    tag-text="READ ONLY"
  >
    <div class="flex gap-2 mb-4">
      <NuxtLink to="/profile/personal" class="px-4 h-9 rounded-[4px] bg-cabin-inset border border-cabin-card/60 text-[11.5px] font-semibold flex items-center text-cabin-muted hover:text-cabin-text">
        Personal Data
      </NuxtLink>
      <NuxtLink to="/profile/psychological" class="px-4 h-9 rounded-[4px] menu-item-active text-[11.5px] font-bold flex items-center text-cabin-text">
        Psychological
      </NuxtLink>
      <NuxtLink to="/profile/physical" class="px-4 h-9 rounded-[4px] bg-cabin-inset border border-cabin-card/60 text-[11.5px] font-semibold flex items-center text-cabin-muted hover:text-cabin-text">
        Physical & Clinical
      </NuxtLink>
    </div>
    <p class="text-[12px] text-cabin-muted">
      14-day Mood and Calmness trend chart and motor reaction latency slot (D3-03).
    </p>
  </ShellHudWindow>
</template>
