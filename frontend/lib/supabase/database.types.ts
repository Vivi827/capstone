export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      activity_events: {
        Row: {
          conversation_id: string | null
          event_id: string
          event_type: string
          feedback_item_id: string | null
          occurred_at: string | null
          received_at: string
          user_id: string
        }
        Insert: {
          conversation_id?: string | null
          event_id: string
          event_type: string
          feedback_item_id?: string | null
          occurred_at?: string | null
          received_at?: string
          user_id: string
        }
        Update: {
          conversation_id?: string | null
          event_id?: string
          event_type?: string
          feedback_item_id?: string | null
          occurred_at?: string | null
          received_at?: string
          user_id?: string
        }
        Relationships: []
      }
      billing_accounts: {
        Row: {
          anchor_at: string | null
          closing: boolean
          cycle: number
          deactivation_pending: boolean
          next_charge_at: string | null
          partner_user_id: string
          product_id: string | null
          renewal_enabled: boolean
          sid: string | null
          trial_used: boolean
          updated_at: string
          user_id: string
        }
        Insert: {
          anchor_at?: string | null
          closing?: boolean
          cycle?: number
          deactivation_pending?: boolean
          next_charge_at?: string | null
          partner_user_id?: string
          product_id?: string | null
          renewal_enabled?: boolean
          sid?: string | null
          trial_used?: boolean
          updated_at?: string
          user_id: string
        }
        Update: {
          anchor_at?: string | null
          closing?: boolean
          cycle?: number
          deactivation_pending?: boolean
          next_charge_at?: string | null
          partner_user_id?: string
          product_id?: string | null
          renewal_enabled?: boolean
          sid?: string | null
          trial_used?: boolean
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      billing_events: {
        Row: {
          payload: Json | null
          provider: string
          provider_event_id: string
          received_at: string
        }
        Insert: {
          payload?: Json | null
          provider: string
          provider_event_id: string
          received_at?: string
        }
        Update: {
          payload?: Json | null
          provider?: string
          provider_event_id?: string
          received_at?: string
        }
        Relationships: []
      }
      billing_orders: {
        Row: {
          amount: number
          approved_at: string | null
          callback_state: string | null
          cancel_url: string | null
          checkout_url: string | null
          created_at: string
          due_at: string | null
          expires_at: string
          id: string
          idempotency_key: string
          kind: string
          mobile_url: string | null
          partner_user_id: string
          product_id: string
          receipt: Json | null
          status: string
          success_url: string | null
          tid: string | null
          trial_days: number
          updated_at: string
          user_id: string
        }
        Insert: {
          amount: number
          approved_at?: string | null
          callback_state?: string | null
          cancel_url?: string | null
          checkout_url?: string | null
          created_at?: string
          due_at?: string | null
          expires_at?: string
          id?: string
          idempotency_key: string
          kind: string
          mobile_url?: string | null
          partner_user_id: string
          product_id: string
          receipt?: Json | null
          status?: string
          success_url?: string | null
          tid?: string | null
          trial_days?: number
          updated_at?: string
          user_id: string
        }
        Update: {
          amount?: number
          approved_at?: string | null
          callback_state?: string | null
          cancel_url?: string | null
          checkout_url?: string | null
          created_at?: string
          due_at?: string | null
          expires_at?: string
          id?: string
          idempotency_key?: string
          kind?: string
          mobile_url?: string | null
          partner_user_id?: string
          product_id?: string
          receipt?: Json | null
          status?: string
          success_url?: string | null
          tid?: string | null
          trial_days?: number
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "billing_orders_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "billing_accounts"
            referencedColumns: ["user_id"]
          },
        ]
      }
      daily_task_snapshots: {
        Row: {
          date_kst: string
          generated_at: string
          task_ids: string[]
          user_id: string
        }
        Insert: {
          date_kst: string
          generated_at?: string
          task_ids: string[]
          user_id: string
        }
        Update: {
          date_kst?: string
          generated_at?: string
          task_ids?: string[]
          user_id?: string
        }
        Relationships: []
      }
      deletion_requests: {
        Row: {
          purge_after: string
          reauth_method: string | null
          requested_at: string
          status: string
          updated_at: string
          user_id: string
        }
        Insert: {
          purge_after: string
          reauth_method?: string | null
          requested_at?: string
          status?: string
          updated_at?: string
          user_id: string
        }
        Update: {
          purge_after?: string
          reauth_method?: string | null
          requested_at?: string
          status?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      messages: {
        Row: {
          axes: Json | null
          character: Json | null
          created_at: string
          feedback: Json | null
          id: string
          idempotency_key: string | null
          role: string
          session_id: string
          transcript: string
        }
        Insert: {
          axes?: Json | null
          character?: Json | null
          created_at?: string
          feedback?: Json | null
          id?: string
          idempotency_key?: string | null
          role: string
          session_id: string
          transcript: string
        }
        Update: {
          axes?: Json | null
          character?: Json | null
          created_at?: string
          feedback?: Json | null
          id?: string
          idempotency_key?: string | null
          role?: string
          session_id?: string
          transcript?: string
        }
        Relationships: [
          {
            foreignKeyName: "messages_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
        ]
      }
      profiles: {
        Row: {
          created_at: string
          display_name: string
          english_level: string
          id: string
          onboarding_completed: boolean
          traits: string[]
          updated_at: string
        }
        Insert: {
          created_at?: string
          display_name?: string
          english_level?: string
          id: string
          onboarding_completed?: boolean
          traits?: string[]
          updated_at?: string
        }
        Update: {
          created_at?: string
          display_name?: string
          english_level?: string
          id?: string
          onboarding_completed?: boolean
          traits?: string[]
          updated_at?: string
        }
        Relationships: []
      }
      sessions: {
        Row: {
          character_name: string
          created_at: string
          ended_at: string | null
          id: string
          level: string
          reopen_count: number
          reopened_at: string | null
          user_id: string | null
        }
        Insert: {
          character_name?: string
          created_at?: string
          ended_at?: string | null
          id?: string
          level?: string
          reopen_count?: number
          reopened_at?: string | null
          user_id?: string | null
        }
        Update: {
          character_name?: string
          created_at?: string
          ended_at?: string | null
          id?: string
          level?: string
          reopen_count?: number
          reopened_at?: string | null
          user_id?: string | null
        }
        Relationships: []
      }
      streak_days: {
        Row: {
          date_kst: string
          qualified: boolean
          user_id: string
        }
        Insert: {
          date_kst: string
          qualified?: boolean
          user_id: string
        }
        Update: {
          date_kst?: string
          qualified?: boolean
          user_id?: string
        }
        Relationships: []
      }
      subscriptions: {
        Row: {
          current_period_end: string | null
          entitled: boolean
          plan: string
          product_id: string | null
          provider: string | null
          provider_customer_id: string | null
          status: string
          updated_at: string
          user_id: string
          will_renew: boolean
        }
        Insert: {
          current_period_end?: string | null
          entitled?: boolean
          plan?: string
          product_id?: string | null
          provider?: string | null
          provider_customer_id?: string | null
          status?: string
          updated_at?: string
          user_id: string
          will_renew?: boolean
        }
        Update: {
          current_period_end?: string | null
          entitled?: boolean
          plan?: string
          product_id?: string | null
          provider?: string | null
          provider_customer_id?: string | null
          status?: string
          updated_at?: string
          user_id?: string
          will_renew?: boolean
        }
        Relationships: []
      }
      usage_daily: {
        Row: {
          date_kst: string
          used_turns: number
          user_id: string
        }
        Insert: {
          date_kst: string
          used_turns?: number
          user_id: string
        }
        Update: {
          date_kst?: string
          used_turns?: number
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      account_deletion_ready: { Args: never; Returns: boolean }
      billing_begin_checkout: {
        Args: {
          p_callback_state: string
          p_cancel_url: string
          p_idempotency_key: string
          p_product_id: string
          p_success_url: string
          p_user_id: string
        }
        Returns: Json
      }
      billing_claim_approval: { Args: { p_order_id: string }; Returns: boolean }
      billing_claim_renewal: { Args: never; Returns: Json }
      billing_finish_order: {
        Args: {
          p_approved_at: string
          p_order_id: string
          p_sid: string
          p_tid: string
        }
        Returns: undefined
      }
      billing_prepare_account_deletion: {
        Args: { p_user_id: string }
        Returns: undefined
      }
      billing_stop_renewal: { Args: { p_user_id: string }; Returns: string }
      release_turn: {
        Args: { p_date: string; p_user_id: string }
        Returns: undefined
      }
      reserve_turn: {
        Args: { p_date: string; p_limit: number; p_user_id: string }
        Returns: number
      }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends (DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never) = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends (PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never) = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
