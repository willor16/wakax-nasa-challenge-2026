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
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
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
}
