<template>
  <div class="grid grid-cols-1 lg:grid-cols-12 gap-[18px] flex-1">
    <ShellHudWindow
      class="lg:col-span-8"
      title="Crew Health Overview"
      subtitle="Read-only group readiness and key vital signs"
      icon="shield"
      tag-text="READ ONLY"
    >
      <p class="text-[12px] text-cabin-muted">
        Crew cards and readiness gauge module slot (D1-05).
      </p>
    </ShellHudWindow>

    <ShellHudWindow
      class="lg:col-span-4"
      title="Cabin Environment"
      subtitle="Clinical habitat indicators"
      icon="earth"
      tag-text="NOMINAL"
    >
      <p class="text-[12px] text-cabin-muted">
        CO2, ambient noise, cabin temperature, and humidity telemetry slot.
      </p>
    </ShellHudWindow>
  </div>
</template>
