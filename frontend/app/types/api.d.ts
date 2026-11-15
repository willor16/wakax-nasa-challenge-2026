export interface paths {
    "/api/v1/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["health_check_api_v1_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/mission": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["get_mission_summary_api_v1_mission_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/stream/telemetry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["stream_telemetry_api_v1_stream_telemetry_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/crew/profiles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["list_crew_profiles_api_v1_crew_profiles_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
                post: operations["login_with_pin_api_v1_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["get_authenticated_profile_api_v1_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/crew-overview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["get_crew_overview_api_v1_crew_overview_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/crew": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["list_all_crew_api_v1_crew_get"];
        put?: never;
                post: operations["create_crew_member_api_v1_crew_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/crew/{crew_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
                patch: operations["update_crew_member_api_v1_crew__crew_id__patch"];
        trace?: never;
    };
    "/api/v1/crew/{crew_id}/baselines": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["get_crew_baselines_api_v1_crew__crew_id__baselines_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/crew/{crew_id}/baselines/recompute": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
                post: operations["recompute_crew_baselines_api_v1_crew__crew_id__baselines_recompute_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/crew/ground-sync": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
                post: operations["apply_ground_crew_directive_api_v1_crew_ground_sync_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/crew/{crew_id}/profile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["get_crew_profile_api_v1_crew__crew_id__profile_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sleep/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
                post: operations["post_sleep_session_api_v1_sleep_sessions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sleep/{crew_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["get_crew_sleep_monitor_api_v1_sleep__crew_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/vision/{crew_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["get_vision_exam_endpoint_api_v1_vision__crew_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/vision/{crew_id}/review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
                post: operations["create_vision_review_endpoint_api_v1_vision__crew_id__review_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auscultation/samples": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
                post: operations["create_auscultation_sample_endpoint_api_v1_auscultation_samples_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auscultation/samples/{sample_id}/audio": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["stream_auscultation_sample_audio_endpoint_api_v1_auscultation_samples__sample_id__audio_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auscultation/{crew_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["get_auscultation_results_endpoint_api_v1_auscultation__crew_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/metrics/catalog": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["get_metric_catalog_api_v1_metrics_catalog_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/metrics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["list_metrics_api_v1_metrics_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/measurements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["list_measurements_api_v1_measurements_get"];
        put?: never;
                post: operations["ingest_measurements_api_v1_measurements_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/measurements/batch": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
                post: operations["ingest_measurements_batch_alias_api_v1_measurements_batch_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/crew-streaks": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["get_crew_streaks_api_v1_crew_streaks_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/comms": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["get_comms_status_api_v1_comms_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/comms/packets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
                post: operations["queue_outbound_packet_api_v1_comms_packets_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/comms/directives": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
                post: operations["receive_ground_directive_api_v1_comms_directives_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/comms/flush": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
                post: operations["flush_outbound_queue_api_v1_comms_flush_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/alerts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["list_alerts_api_v1_alerts_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/alerts/{alert_id}/acknowledge": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
                post: operations["acknowledge_alert_api_v1_alerts__alert_id__acknowledge_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/psych/checkins": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
                post: operations["create_checkin_api_v1_psych_checkins_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/cognitive/sessions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
                post: operations["create_reaction_session_api_v1_cognitive_sessions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/psych/profile": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["get_psych_profile_api_v1_psych_profile_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/wiki/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["search_guide_api_v1_wiki_search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/wiki/emergency-index": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["get_emergency_index_api_v1_wiki_emergency_index_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/wiki/articles/{article_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["get_guide_article_api_v1_wiki_articles__article_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/kit/drawers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["get_kit_drawers_api_v1_kit_drawers_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/diagnosis/anomalies": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
                post: operations["scan_for_anomalies_api_v1_diagnosis_anomalies_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/diagnosis": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
                get: operations["get_diagnoses_api_v1_diagnosis_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/diagnosis/{diagnosis_id}/review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
                post: operations["review_api_v1_diagnosis__diagnosis_id__review_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
                AuscultationCo2PointOut: {
                        label: string;
                        co2_mmhg: number;
                        co2_ppm: number;
        };
                AuscultationMetricBarOut: {
                        key: string;
                        label: string;
                        target_label: string;
                        display_value: string;
                        fill_pct: number;
                        tone: "nominal" | "warn" | "critical";
        };
                AuscultationOrganSummaryOut: {
                        organ_type: "CARDIAC" | "PULMONARY";
                        title: string;
                        primary_metric: string;
                        secondary_badge: string;
                        sites_summary: string;
                        detail_line: string;
                        tone: "reference" | "warn" | "critical";
                        saved_sites_count: number;
                        total_sites_count: number;
                        latest_sample_id?: number | null;
        };
                AuscultationResultsOut: {
                        crew_id: string;
                        crew_code: string;
                        full_name: string;
                        role: string;
                        selected_stage: "ALL" | "LAUNCH" | "MISSION" | "RETURN";
                        active_mission_stage: string;
                        stage_has_records: boolean;
                        overall_tone: "reference" | "warn" | "critical";
                        results_badge: string;
                        signal_quality_pct: number;
                        signal_badge: string;
                        cabin_noise_dba: number;
                        noise_gate_limit_dba: number;
                        is_noise_safe: boolean;
                        heart_rate_bpm: number;
                        respiratory_rate_rpm: number;
                        spo2_pct: number;
            cardiac_summary: components["schemas"]["AuscultationOrganSummaryOut"];
            pulmonary_summary: components["schemas"]["AuscultationOrganSummaryOut"];
                        clinical_bars: components["schemas"]["AuscultationMetricBarOut"][];
                        cardiac_channel_subtitle: string;
                        pulmonary_channel_subtitle: string;
                        phonocardiogram_samples: number[];
                        pulmonary_envelope_samples: number[];
                        co2_badge: string;
                        co2_tone: "reference" | "warn" | "critical";
                        co2_current_mmhg: number;
                        co2_target_max_mmhg: number;
                        co2_alert_limit_mmhg: number;
                        co2_trend: components["schemas"]["AuscultationCo2PointOut"][];
                        cardiac_sites: components["schemas"]["AuscultationSiteStatusOut"][];
                        pulmonary_sites: components["schemas"]["AuscultationSiteStatusOut"][];
                        cardiac_progress_summary: string;
                        pulmonary_progress_summary: string;
        };
                AuscultationSampleCreatedOut: {
                        sample_id: number;
                        crew_id: string;
                        mission_stage: "LAUNCH" | "MISSION" | "RETURN";
                        organ_type: "CARDIAC" | "PULMONARY";
                        anatomical_site: "aortic" | "pulmonic" | "tricuspid" | "mitral" | "upper_left" | "upper_right" | "lower_left" | "lower_right";
                        duration_sec: number;
                        cabin_noise_dba: number;
                        file_rel_path: string;
                        sha256_hex: string;
                        recorded_at_utc: string;
                        signal_quality_pct: number;
                        streak: {
                [key: string]: unknown;
            };
        };
                AuscultationSiteStatusOut: {
                        site_key: "aortic" | "pulmonic" | "tricuspid" | "mitral" | "upper_left" | "upper_right" | "lower_left" | "lower_right";
                        organ_type: "CARDIAC" | "PULMONARY";
                        short_label: string;
                        placement_title: string;
                        saved: boolean;
                        duration_sec?: number | null;
                        sample_id?: number | null;
                        recorded_at_utc?: string | null;
                        status_text: string;
        };
                BiometricCardOut: {
                        key: string;
                        label: string;
                        value: number;
                        display_value: string;
                        unit: string;
                        baseline_mean: number | null;
                        baseline_std: number | null;
                        z_score: number | null;
                        subtitle: string;
                        status_tone: "nominal" | "warn" | "critical";
        };
                BiometricScanOut: {
                        scan_label: string;
                        scan_tone: "reference" | "warn" | "critical";
                        core_temp_c: number;
                        core_temp_display: string;
                        hydration_liters: number;
                        hydration_target_liters: number;
                        hydration_display: string;
                        cardiac_tone: "nominal" | "warn" | "critical";
                        pulmonary_tone: "nominal" | "warn" | "critical";
                        ocular_tone: "nominal" | "warn" | "critical";
        };
                Body_create_auscultation_sample_endpoint_api_v1_auscultation_samples_post: {
                        crew_id: string;
                        organ_type: "CARDIAC" | "PULMONARY";
                        anatomical_site: "aortic" | "pulmonic" | "tricuspid" | "mitral" | "upper_left" | "upper_right" | "lower_left" | "lower_right";
                        duration_sec: number;
                        cabin_noise_dba: number;
                        sha256_hex: string;
                        audio_file: string;
                        mission_stage: "LAUNCH" | "MISSION" | "RETURN";
        };
                CheckinIn: {
                        mood_state?: ("CALM" | "FOCUSED" | "TIRED" | "STRESSED") | null;
                        mood: number;
                        stress: number;
                        isolation: number;
                        motivation: number;
                        sleep_onset_utc?: string | null;
                        wake_utc?: string | null;
        };
                ClinicalLabCardOut: {
                        key: string;
                        label: string;
                        status_label: string;
                        status_tone: "nominal" | "warn" | "critical";
                        display_value: string;
                        detail: string;
        };
                ClinicalProgressItemOut: {
                        key: string;
                        label: string;
                        subtitle: string;
                        display_value: string;
                        unit: string;
                        status_label: string;
                        status_tone: "nominal" | "warn" | "critical";
                        progress_pct: number;
                        band_start_pct: number;
                        band_width_pct: number;
                        on_target: boolean;
        };
                CrewCreateIn: {
                        id: string;
                        code: string;
                        full_name: string;
                        role: "ASTRONAUT" | "PILOT" | "OPERATOR" | "PHYSICIAN";
                        pin: string;
                        age?: number | null;
                        sex?: ("F" | "M" | "X") | null;
                        blood_type?: string | null;
                        height_cm?: number | null;
        };
                CrewDemographicsOut: {
                        id: string;
                        code: string;
                        full_name: string;
                        short_name: string;
                        role: "ASTRONAUT" | "PILOT" | "OPERATOR" | "PHYSICIAN";
                        role_badge: string;
                        age: number | null;
                        sex: string | null;
                        sex_display: string;
                        blood_type: string | null;
                        baseline_height_cm: number;
        };
                CrewProfileOut: {
            crew: components["schemas"]["CrewDemographicsOut"];
            mission: components["schemas"]["ProfileMissionContextOut"];
                        stage_comparison: components["schemas"]["StageMetricSnapshotOut"][];
                        biometrics: components["schemas"]["BiometricCardOut"][];
            biometric_scan: components["schemas"]["BiometricScanOut"];
            environment_work: components["schemas"]["EnvironmentAndWorkOut"];
            daily_vitals: components["schemas"]["DailyVitalsHabitsOut"];
            live_ecg: components["schemas"]["LiveEcgOut"];
                        clinical_labs: components["schemas"]["ClinicalLabCardOut"][];
        };
                CrewUpdateIn: {
                        full_name?: string | null;
                        role?: ("ASTRONAUT" | "PILOT" | "OPERATOR" | "PHYSICIAN") | null;
                        pin?: string | null;
                        age?: number | null;
                        sex?: ("F" | "M" | "X") | null;
                        blood_type?: string | null;
                        height_cm?: number | null;
                        is_active?: boolean | null;
                        unlock_account: boolean;
        };
                DailyVitalsHabitsOut: {
                        tag_text: string;
                        header_target_badge: string;
                        on_target_count: number;
                        total_count: number;
                        items: components["schemas"]["ClinicalProgressItemOut"][];
        };
                EnvironmentAndWorkOut: {
                        habitat_tag: string;
                        co2_ppm: number;
                        co2_mmhg: number;
                        radiation_msv: number;
                        solar_event_flag: boolean;
                        gauges: components["schemas"]["EnvironmentGaugeOut"][];
                        work_header: string;
                        work_rows: components["schemas"]["WorkTimeRowOut"][];
        };
                EnvironmentGaugeOut: {
                        key: string;
                        label: string;
                        value: number;
                        display_value: string;
                        subtitle: string;
                        arc_pct: number;
                        status_tone: "nominal" | "warn" | "critical";
        };
                GroundCrewDirectiveIn: {
                        action: "CREATE" | "UPDATE" | "DEACTIVATE";
                        crew_id: string;
                        code?: string | null;
                        full_name?: string | null;
                        role?: ("ASTRONAUT" | "PILOT" | "OPERATOR" | "PHYSICIAN") | null;
                        pin?: string | null;
        };
                HTTPValidationError: {
                        detail?: components["schemas"]["ValidationError"][];
        };
                InboundDirectiveIn: {
                        crew_id?: string | null;
                        title_en: string;
                        guidance_en: string;
        };
                LiveEcgOut: {
                        rhythm_label: string;
                        rhythm_tone: "reference" | "warn" | "critical";
                        lead_label: string;
                        resting_hr_bpm: number;
                        hrv_rmssd_ms: number;
                        body_temp_c: number;
                        header_summary: string;
                        sample_rate_hz: number;
                        samples_mv: number[];
        };
                MeasurementBatchIn: {
                        crew_id: string;
                        mission_stage: "LAUNCH" | "MISSION" | "RETURN";
                        source_type: "MANUAL" | "AUTO";
                        recorded_at_utc?: string | null;
                        items: components["schemas"]["MeasurementItemIn"][];
        };
                MeasurementIngestOut: {
                        inserted_ids: number[];
                        alerts_created: number[];
            streak: components["schemas"]["StreakUpdateSummary"];
                        recorded_at_utc: string;
        };
                MeasurementItemIn: {
                        metric_key: string;
                        value_num: number;
                        payload_json?: {
                [key: string]: unknown;
            };
        };
                MeasurementRowOut: {
                        id: number;
                        crew_id: string;
                        metric_key: string;
                        mission_stage: "LAUNCH" | "MISSION" | "RETURN";
                        source_type: "MANUAL" | "AUTO";
                        recorded_at_utc: string;
                        value_num?: number | null;
                        payload_json: string;
        };
                MetricCatalogItem: {
                        metric_key: string;
                        display_name_en: string;
                        category: "VITALS" | "BIOMETRICS" | "HABITS" | "LABS" | "VISION" | "RESPIRATORY" | "ENVIRONMENT";
                        unit: string;
                        nominal_min: number;
                        nominal_max: number;
                        warning_min?: number | null;
                        warning_max?: number | null;
                        critical_min?: number | null;
                        critical_threshold?: number | null;
                        recommended_frequency_hours: number;
                        clinical_reference: string;
        };
                PinLoginRequest: {
                        crew_id: string;
                        pin: string;
        };
                ProfileMissionContextOut: {
                        mission_code: string;
                        mission_name: string;
                        current_stage: "LAUNCH" | "MISSION" | "RETURN";
                        selected_stage: "LAUNCH" | "MISSION" | "RETURN";
                        stage_has_records: boolean;
                        mission_day: number;
                        mission_day_code: string;
                        elapsed_days_label: string;
                        utc_hm: string;
                        server_utc: string;
        };
                QueuePacketIn: {
                        crew_id: string | null;
                        packet_type: "DAILY_SUMMARY" | "CLINICAL_REPORT";
                        note_en?: string | null;
        };
                ReactionSessionIn: {
                        reaction_times_ms: (number | null)[];
                        false_starts: number;
                        duration_sec: number;
        };
                ReviewIn: {
                        decision: "APPROVED" | "REJECTED" | "PROMOTED_TO_GUIDE";
                        notes_en?: string | null;
        };
                ScanIn: {
                        crew_id?: string | null;
        };
                SleepAxisTickOut: {
                        offset_min: number;
                        label: string;
        };
                SleepMonitorOut: {
                        crew_id: string;
                        crew_code: string;
                        period: "last_night" | "7d" | "14d" | "30d";
                        nights_analyzed: number;
                        mission_day: number;
                        last_night_tab_label: string;
                        rest_window_badge: string;
                        header_score_badge: string;
                        quality_tag: string;
                        quality_tone: "reference" | "warn" | "critical";
                        sleep_score: number;
                        score_subtitle: string;
                        sleep_time_heading: string;
                        total_sleep_min: number;
                        total_sleep_display: string;
                        target_label: string;
                        target_met: boolean;
                        in_bed_min: number;
                        in_bed_display: string;
                        efficiency_pct: number;
                        efficiency_label: string;
                        stage_cards: components["schemas"]["SleepStageCardOut"][];
                        ribbon_title: string;
                        cycle_count: number;
                        cycle_badge: string;
                        rest_window_inline: string;
                        window_total_min: number;
                        axis_ticks: components["schemas"]["SleepAxisTickOut"][];
                        ribbon_legend: components["schemas"]["SleepRibbonLegendItemOut"][];
                        ribbon_bouts: components["schemas"]["SleepRibbonBoutOut"][];
                        total_bouts: number;
                        bouts_badge: string;
                        lapse_rows: components["schemas"]["SleepStageLapseRowOut"][];
        };
                SleepRibbonBoutOut: {
                        stage: "DEEP" | "REM" | "LIGHT" | "AWAKE";
                        lane_index: number;
                        prev_lane_index?: number | null;
                        start_offset_min: number;
                        end_offset_min: number;
                        duration_min: number;
                        start_hm: string;
                        end_hm: string;
        };
                SleepRibbonLegendItemOut: {
                        stage: "DEEP" | "REM" | "LIGHT" | "AWAKE";
                        label: string;
        };
                SleepSessionCreateIn: {
                        crew_id: string;
                        mission_stage: "LAUNCH" | "MISSION" | "RETURN";
                        sleep_start_utc: string;
                        sleep_end_utc: string;
                        deep_min?: number | null;
                        rem_min?: number | null;
                        light_min?: number | null;
                        awake_min?: number | null;
                        sleep_score?: number | null;
                        stages?: components["schemas"]["SleepStageBoutIn"][] | null;
        };
                SleepSessionCreatedOut: {
                        session_id: number;
                        crew_id: string;
                        mission_stage: "LAUNCH" | "MISSION" | "RETURN";
                        sleep_start_utc: string;
                        sleep_end_utc: string;
                        total_sleep_min: number;
                        time_in_bed_min: number;
                        sleep_score: number;
                        sleep_efficiency_pct: number;
                        bouts_inserted: number;
        };
                SleepStageBoutIn: {
                        stage: "DEEP" | "REM" | "LIGHT" | "AWAKE";
                        start_utc: string;
                        end_utc: string;
                        duration_min?: number | null;
        };
                SleepStageCardOut: {
                        stage: "DEEP" | "REM" | "LIGHT" | "AWAKE";
                        label: string;
                        duration_min: number;
                        duration_display: string;
                        badge_label: string;
                        badge_tone: "reference" | "warn" | "critical";
                        share_pct: number;
                        subtitle: string;
                        bar_fill_pct: number;
        };
                SleepStageLapseRowOut: {
                        stage: "DEEP" | "REM" | "LIGHT" | "AWAKE";
                        label: string;
                        intervals_summary: string;
                        bouts_count: number;
                        bouts_label: string;
                        avg_max_label: string;
                        total_display: string;
        };
                StageMetricSnapshotOut: {
                        stage: "LAUNCH" | "MISSION" | "RETURN";
                        has_records: boolean;
                        body_weight_kg: number | null;
                        resting_hr_bpm: number | null;
                        vo2_max_ml_kg_min: number | null;
                        optic_sheath_right_mm: number | null;
        };
                StreakUpdateSummary: {
                        crew_id: string;
                        streak_date_utc: string;
                        logs_completed: number;
                        habits_met: boolean;
                        daily_compliant: boolean;
        };
                ValidationError: {
                        loc: (string | number)[];
                        msg: string;
                        type: string;
                        input?: unknown;
                        ctx?: Record<string, never>;
        };
                VisionClinicalMetricOut: {
                        key: string;
                        label: string;
                        subtitle: string;
                        display_value: string;
                        unit: string;
                        badge_label: string;
                        tone: "nominal" | "warn" | "critical";
                        marker_pct: number;
                        nominal_band_start_pct: number;
                        nominal_band_width_pct: number;
        };
                VisionExamOut: {
                        crew_id: string;
                        crew_code: string;
                        selected_stage: "ALL" | "LAUNCH" | "MISSION" | "RETURN";
                        stage_has_records: boolean;
                        mission_day: number;
                        header_status_badge: string;
                        overall_tone: "reference" | "warn" | "critical";
                        alert_headline: string;
                        review_status: "PENDING_REVIEW" | "APPROVED" | "REJECTED" | "PROMOTED_TO_GUIDE";
                        reviewed_by_label: string;
                        physician_notes_en?: string | null;
            left_eye: components["schemas"]["VisionEyeArcOut"];
            right_eye: components["schemas"]["VisionEyeArcOut"];
                        ocular_metrics: components["schemas"]["VisionClinicalMetricOut"][];
                        latest_scan_heading: string;
                        latest_scan_subtitle: string;
                        baseline_band_label: string;
                        baseline_band_min_mm: number;
                        baseline_band_max_mm: number;
                        alert_threshold_label: string;
                        alert_threshold_mm: number;
                        right_legend_label: string;
                        left_legend_label: string;
                        trend_points: components["schemas"]["VisionTrendPointOut"][];
                        steps_badge: string;
                        preventive_steps: components["schemas"]["VisionPreventiveStepOut"][];
        };
                VisionEyeArcOut: {
                        side: "LEFT" | "RIGHT";
                        label: string;
                        sheath_mm: number;
                        display_value: string;
                        baseline_mm: number;
                        delta_mm: number;
                        status_label: string;
                        tone: "reference" | "warn" | "critical";
        };
                VisionPreventiveStepIn: {
                        step_number: number;
                        code_label: string;
                        title: string;
                        description: string;
                        accent_tone: "ok" | "ice";
        };
                VisionPreventiveStepOut: {
                        step_number: number;
                        code_label: string;
                        title: string;
                        description: string;
                        accent_tone: "ok" | "ice";
        };
                VisionReviewCreateIn: {
                        validation_status: "APPROVED" | "REJECTED" | "PROMOTED_TO_GUIDE";
                        physician_notes_en?: string | null;
                        preventive_steps?: components["schemas"]["VisionPreventiveStepIn"][] | null;
        };
                VisionReviewCreatedOut: {
                        diagnosis_id: number;
                        crew_id: string;
                        validation_status: "PENDING_REVIEW" | "APPROVED" | "REJECTED" | "PROMOTED_TO_GUIDE";
                        validated_by: string;
                        reviewer_label: string;
                        validated_at_utc: string;
                        physician_notes_en?: string | null;
        };
                VisionTrendPointOut: {
                        label: string;
                        left_mm: number;
                        right_mm: number;
                        is_projected: boolean;
        };
                WorkTimeRowOut: {
                        key: string;
                        label: string;
                        subtitle: string;
                        display_value: string;
                        status_tone: "nominal" | "warn" | "critical";
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    health_check_api_v1_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
        };
    };
    get_mission_summary_api_v1_mission_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    stream_telemetry_api_v1_stream_telemetry_get: {
        parameters: {
            query?: {
                crew_id?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_crew_profiles_api_v1_crew_profiles_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    }[];
                };
            };
        };
    };
    login_with_pin_api_v1_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PinLoginRequest"];
            };
        };
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_authenticated_profile_api_v1_auth_me_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_crew_overview_api_v1_crew_overview_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    list_all_crew_api_v1_crew_get: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    }[];
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_crew_member_api_v1_crew_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CrewCreateIn"];
            };
        };
        responses: {
                        201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_crew_member_api_v1_crew__crew_id__patch: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                crew_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CrewUpdateIn"];
            };
        };
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_crew_baselines_api_v1_crew__crew_id__baselines_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                crew_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    }[];
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    recompute_crew_baselines_api_v1_crew__crew_id__baselines_recompute_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                crew_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    apply_ground_crew_directive_api_v1_crew_ground_sync_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GroundCrewDirectiveIn"];
            };
        };
        responses: {
                        202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_crew_profile_api_v1_crew__crew_id__profile_get: {
        parameters: {
            query?: {
                stage?: ("LAUNCH" | "MISSION" | "RETURN") | null;
            };
            header?: never;
            path: {
                crew_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CrewProfileOut"];
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    post_sleep_session_api_v1_sleep_sessions_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SleepSessionCreateIn"];
            };
        };
        responses: {
                        201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SleepSessionCreatedOut"];
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_crew_sleep_monitor_api_v1_sleep__crew_id__get: {
        parameters: {
            query?: {
                period?: "last_night" | "7d" | "14d" | "30d";
            };
            header?: never;
            path: {
                crew_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SleepMonitorOut"];
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_vision_exam_endpoint_api_v1_vision__crew_id__get: {
        parameters: {
            query?: {
                stage?: "ALL" | "LAUNCH" | "MISSION" | "RETURN";
            };
            header?: never;
            path: {
                crew_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VisionExamOut"];
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_vision_review_endpoint_api_v1_vision__crew_id__review_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                crew_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["VisionReviewCreateIn"];
            };
        };
        responses: {
                        201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VisionReviewCreatedOut"];
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_auscultation_sample_endpoint_api_v1_auscultation_samples_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_create_auscultation_sample_endpoint_api_v1_auscultation_samples_post"];
            };
        };
        responses: {
                        201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuscultationSampleCreatedOut"];
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    stream_auscultation_sample_audio_endpoint_api_v1_auscultation_samples__sample_id__audio_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sample_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_auscultation_results_endpoint_api_v1_auscultation__crew_id__get: {
        parameters: {
            query?: {
                stage?: "ALL" | "LAUNCH" | "MISSION" | "RETURN";
            };
            header?: never;
            path: {
                crew_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuscultationResultsOut"];
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_metric_catalog_api_v1_metrics_catalog_get: {
        parameters: {
            query?: {
                category?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MetricCatalogItem"][];
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_metrics_api_v1_metrics_get: {
        parameters: {
            query?: {
                category?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MetricCatalogItem"][];
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_measurements_api_v1_measurements_get: {
        parameters: {
            query: {
                crew_id: string;
                metric_key?: string | null;
                category?: string | null;
                mission_stage?: ("LAUNCH" | "MISSION" | "RETURN") | null;
                source_type?: ("MANUAL" | "AUTO") | null;
                from_utc?: string | null;
                to_utc?: string | null;
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeasurementRowOut"][];
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ingest_measurements_api_v1_measurements_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MeasurementBatchIn"];
            };
        };
        responses: {
                        201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeasurementIngestOut"];
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ingest_measurements_batch_alias_api_v1_measurements_batch_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MeasurementBatchIn"];
            };
        };
        responses: {
                        201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MeasurementIngestOut"];
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_crew_streaks_api_v1_crew_streaks_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_comms_status_api_v1_comms_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    queue_outbound_packet_api_v1_comms_packets_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["QueuePacketIn"];
            };
        };
        responses: {
                        201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    receive_ground_directive_api_v1_comms_directives_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InboundDirectiveIn"];
            };
        };
        responses: {
                        201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    flush_outbound_queue_api_v1_comms_flush_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: number;
                    };
                };
            };
        };
    };
    list_alerts_api_v1_alerts_get: {
        parameters: {
            query?: {
                view?: "all" | "advisories" | "checks";
                include_acknowledged?: boolean;
            };
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    acknowledge_alert_api_v1_alerts__alert_id__acknowledge_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                alert_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_checkin_api_v1_psych_checkins_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CheckinIn"];
            };
        };
        responses: {
                        201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_reaction_session_api_v1_cognitive_sessions_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReactionSessionIn"];
            };
        };
        responses: {
                        201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_psych_profile_api_v1_psych_profile_get: {
        parameters: {
            query?: {
                days?: number;
            };
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    search_guide_api_v1_wiki_search_get: {
        parameters: {
            query?: {
                q?: string;
                category?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_emergency_index_api_v1_wiki_emergency_index_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    get_guide_article_api_v1_wiki_articles__article_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                article_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_kit_drawers_api_v1_kit_drawers_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
        };
    };
    scan_for_anomalies_api_v1_diagnosis_anomalies_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScanIn"];
            };
        };
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_diagnoses_api_v1_diagnosis_get: {
        parameters: {
            query?: {
                status?: ("PENDING_REVIEW" | "APPROVED" | "REJECTED" | "PROMOTED_TO_GUIDE") | null;
            };
            header?: {
                authorization?: string | null;
            };
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    review_api_v1_diagnosis__diagnosis_id__review_post: {
        parameters: {
            query?: never;
            header?: {
                authorization?: string | null;
            };
            path: {
                diagnosis_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReviewIn"];
            };
        };
        responses: {
                        200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
                        422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
