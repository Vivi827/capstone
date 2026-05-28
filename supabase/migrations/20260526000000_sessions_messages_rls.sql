-- Phase 1C follow-up: explicit RLS policies for sessions/messages
-- This migration adds row-level security policies so Supabase access
-- is gated and future authenticated session ownership can be enforced.

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS user_id UUID;

-- Service role bypasses RLS automatically, so the policies below only
-- matter for non-service-role Supabase clients.
CREATE POLICY "allow_service_role_all_sessions"
    ON sessions FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "allow_authenticated_session_owner_select"
    ON sessions FOR SELECT
    USING (
        auth.role() = 'authenticated' AND auth.uid() = user_id
    );

CREATE POLICY "allow_authenticated_session_owner_insert"
    ON sessions FOR INSERT
    WITH CHECK (
        auth.role() = 'authenticated' AND auth.uid() = user_id
    );

CREATE POLICY "allow_authenticated_session_owner_update"
    ON sessions FOR UPDATE
    USING (
        auth.role() = 'authenticated' AND auth.uid() = user_id
    )
    WITH CHECK (
        auth.role() = 'authenticated' AND auth.uid() = user_id
    );

CREATE POLICY "allow_authenticated_session_owner_delete"
    ON sessions FOR DELETE
    USING (
        auth.role() = 'authenticated' AND auth.uid() = user_id
    );

CREATE POLICY "allow_service_role_all_messages"
    ON messages FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

CREATE POLICY "allow_authenticated_messages_for_own_session_select"
    ON messages FOR SELECT
    USING (
        auth.role() = 'authenticated' AND
        EXISTS (
            SELECT 1 FROM sessions
            WHERE sessions.id = messages.session_id
              AND sessions.user_id = auth.uid()
        )
    );

CREATE POLICY "allow_authenticated_messages_for_own_session_insert"
    ON messages FOR INSERT
    WITH CHECK (
        auth.role() = 'authenticated' AND
        EXISTS (
            SELECT 1 FROM sessions
            WHERE sessions.id = messages.session_id
              AND sessions.user_id = auth.uid()
        )
    );

CREATE POLICY "allow_authenticated_messages_for_own_session_update"
    ON messages FOR UPDATE
    USING (
        auth.role() = 'authenticated' AND
        EXISTS (
            SELECT 1 FROM sessions
            WHERE sessions.id = messages.session_id
              AND sessions.user_id = auth.uid()
        )
    )
    WITH CHECK (
        auth.role() = 'authenticated' AND
        EXISTS (
            SELECT 1 FROM sessions
            WHERE sessions.id = messages.session_id
              AND sessions.user_id = auth.uid()
        )
    );

CREATE POLICY "allow_authenticated_messages_for_own_session_delete"
    ON messages FOR DELETE
    USING (
        auth.role() = 'authenticated' AND
        EXISTS (
            SELECT 1 FROM sessions
            WHERE sessions.id = messages.session_id
              AND sessions.user_id = auth.uid()
        )
    );
