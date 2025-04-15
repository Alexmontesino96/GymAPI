--
-- PostgreSQL database dump
--

-- Dumped from database version 15.8
-- Dumped by pg_dump version 15.12 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

DROP EVENT TRIGGER IF EXISTS pgrst_drop_watch;
DROP EVENT TRIGGER IF EXISTS pgrst_ddl_watch;
DROP EVENT TRIGGER IF EXISTS issue_pg_net_access;
DROP EVENT TRIGGER IF EXISTS issue_pg_graphql_access;
DROP EVENT TRIGGER IF EXISTS issue_pg_cron_access;
DROP EVENT TRIGGER IF EXISTS issue_graphql_placeholder;
DROP PUBLICATION IF EXISTS supabase_realtime;
ALTER TABLE IF EXISTS ONLY storage.s3_multipart_uploads_parts DROP CONSTRAINT IF EXISTS s3_multipart_uploads_parts_upload_id_fkey;
ALTER TABLE IF EXISTS ONLY storage.s3_multipart_uploads_parts DROP CONSTRAINT IF EXISTS s3_multipart_uploads_parts_bucket_id_fkey;
ALTER TABLE IF EXISTS ONLY storage.s3_multipart_uploads DROP CONSTRAINT IF EXISTS s3_multipart_uploads_bucket_id_fkey;
ALTER TABLE IF EXISTS ONLY storage.objects DROP CONSTRAINT IF EXISTS "objects_bucketId_fkey";
ALTER TABLE IF EXISTS ONLY public.user_gyms DROP CONSTRAINT IF EXISTS user_gyms_user_id_fkey;
ALTER TABLE IF EXISTS ONLY public.user_gyms DROP CONSTRAINT IF EXISTS user_gyms_gym_id_fkey;
ALTER TABLE IF EXISTS ONLY public.trainermemberrelationship DROP CONSTRAINT IF EXISTS trainermemberrelationship_trainer_id_fkey;
ALTER TABLE IF EXISTS ONLY public.trainermemberrelationship DROP CONSTRAINT IF EXISTS trainermemberrelationship_member_id_fkey;
ALTER TABLE IF EXISTS ONLY public.trainermemberrelationship DROP CONSTRAINT IF EXISTS trainermemberrelationship_created_by_fkey;
ALTER TABLE IF EXISTS ONLY public.gym_special_hours DROP CONSTRAINT IF EXISTS gym_special_hours_gym_id_fkey;
ALTER TABLE IF EXISTS ONLY public.gym_special_hours DROP CONSTRAINT IF EXISTS gym_special_hours_created_by_fkey;
ALTER TABLE IF EXISTS ONLY public.gym_hours DROP CONSTRAINT IF EXISTS gym_hours_gym_id_fkey;
ALTER TABLE IF EXISTS ONLY public.class_session DROP CONSTRAINT IF EXISTS fk_class_session_gym_id_gyms;
ALTER TABLE IF EXISTS ONLY public.chat_members DROP CONSTRAINT IF EXISTS fk_chat_members_user_id_user;
ALTER TABLE IF EXISTS ONLY public.events DROP CONSTRAINT IF EXISTS events_gym_id_fkey;
ALTER TABLE IF EXISTS ONLY public.events DROP CONSTRAINT IF EXISTS events_creator_id_fkey;
ALTER TABLE IF EXISTS ONLY public.event_participations DROP CONSTRAINT IF EXISTS event_participations_member_id_fkey;
ALTER TABLE IF EXISTS ONLY public.event_participations DROP CONSTRAINT IF EXISTS event_participations_gym_id_fkey;
ALTER TABLE IF EXISTS ONLY public.event_participations DROP CONSTRAINT IF EXISTS event_participations_event_id_fkey;
ALTER TABLE IF EXISTS ONLY public.class_session DROP CONSTRAINT IF EXISTS class_session_trainer_id_fkey;
ALTER TABLE IF EXISTS ONLY public.class_session DROP CONSTRAINT IF EXISTS class_session_created_by_fkey;
ALTER TABLE IF EXISTS ONLY public.class_session DROP CONSTRAINT IF EXISTS class_session_class_id_fkey;
ALTER TABLE IF EXISTS ONLY public.class_participation DROP CONSTRAINT IF EXISTS class_participation_session_id_fkey;
ALTER TABLE IF EXISTS ONLY public.class_participation DROP CONSTRAINT IF EXISTS class_participation_member_id_fkey;
ALTER TABLE IF EXISTS ONLY public.class_participation DROP CONSTRAINT IF EXISTS class_participation_gym_id_fkey;
ALTER TABLE IF EXISTS ONLY public.class DROP CONSTRAINT IF EXISTS class_gym_id_fkey;
ALTER TABLE IF EXISTS ONLY public.class DROP CONSTRAINT IF EXISTS class_created_by_fkey;
ALTER TABLE IF EXISTS ONLY public.class DROP CONSTRAINT IF EXISTS class_category_id_fkey;
ALTER TABLE IF EXISTS ONLY public.class_category_custom DROP CONSTRAINT IF EXISTS class_category_custom_gym_id_fkey;
ALTER TABLE IF EXISTS ONLY public.class_category_custom DROP CONSTRAINT IF EXISTS class_category_custom_created_by_fkey;
ALTER TABLE IF EXISTS ONLY public.chat_rooms DROP CONSTRAINT IF EXISTS chat_rooms_event_id_fkey;
ALTER TABLE IF EXISTS ONLY public.chat_members DROP CONSTRAINT IF EXISTS chat_members_room_id_fkey;
ALTER TABLE IF EXISTS ONLY auth.sso_domains DROP CONSTRAINT IF EXISTS sso_domains_sso_provider_id_fkey;
ALTER TABLE IF EXISTS ONLY auth.sessions DROP CONSTRAINT IF EXISTS sessions_user_id_fkey;
ALTER TABLE IF EXISTS ONLY auth.saml_relay_states DROP CONSTRAINT IF EXISTS saml_relay_states_sso_provider_id_fkey;
ALTER TABLE IF EXISTS ONLY auth.saml_relay_states DROP CONSTRAINT IF EXISTS saml_relay_states_flow_state_id_fkey;
ALTER TABLE IF EXISTS ONLY auth.saml_providers DROP CONSTRAINT IF EXISTS saml_providers_sso_provider_id_fkey;
ALTER TABLE IF EXISTS ONLY auth.refresh_tokens DROP CONSTRAINT IF EXISTS refresh_tokens_session_id_fkey;
ALTER TABLE IF EXISTS ONLY auth.one_time_tokens DROP CONSTRAINT IF EXISTS one_time_tokens_user_id_fkey;
ALTER TABLE IF EXISTS ONLY auth.mfa_factors DROP CONSTRAINT IF EXISTS mfa_factors_user_id_fkey;
ALTER TABLE IF EXISTS ONLY auth.mfa_challenges DROP CONSTRAINT IF EXISTS mfa_challenges_auth_factor_id_fkey;
ALTER TABLE IF EXISTS ONLY auth.mfa_amr_claims DROP CONSTRAINT IF EXISTS mfa_amr_claims_session_id_fkey;
ALTER TABLE IF EXISTS ONLY auth.identities DROP CONSTRAINT IF EXISTS identities_user_id_fkey;
DROP TRIGGER IF EXISTS update_objects_updated_at ON storage.objects;
DROP TRIGGER IF EXISTS tr_check_filters ON realtime.subscription;
DROP INDEX IF EXISTS storage.name_prefix_search;
DROP INDEX IF EXISTS storage.idx_objects_bucket_id_name;
DROP INDEX IF EXISTS storage.idx_multipart_uploads_list;
DROP INDEX IF EXISTS storage.bucketid_objname;
DROP INDEX IF EXISTS storage.bname;
DROP INDEX IF EXISTS realtime.subscription_subscription_id_entity_filters_key;
DROP INDEX IF EXISTS realtime.ix_realtime_subscription_entity;
DROP INDEX IF EXISTS public.ix_user_last_name;
DROP INDEX IF EXISTS public.ix_user_id;
DROP INDEX IF EXISTS public.ix_user_gyms_id;
DROP INDEX IF EXISTS public.ix_user_first_name;
DROP INDEX IF EXISTS public.ix_user_email;
DROP INDEX IF EXISTS public.ix_user_auth0_id;
DROP INDEX IF EXISTS public.ix_trainermemberrelationship_id;
DROP INDEX IF EXISTS public.ix_gyms_subdomain;
DROP INDEX IF EXISTS public.ix_gyms_id;
DROP INDEX IF EXISTS public.ix_gym_special_hours_id;
DROP INDEX IF EXISTS public.ix_gym_special_hours_gym_id;
DROP INDEX IF EXISTS public.ix_gym_special_hours_date;
DROP INDEX IF EXISTS public.ix_gym_hours_id;
DROP INDEX IF EXISTS public.ix_events_status;
DROP INDEX IF EXISTS public.ix_events_start_time;
DROP INDEX IF EXISTS public.ix_events_id;
DROP INDEX IF EXISTS public.ix_events_gym_status;
DROP INDEX IF EXISTS public.ix_events_gym_id;
DROP INDEX IF EXISTS public.ix_events_gym_dates;
DROP INDEX IF EXISTS public.ix_events_end_time;
DROP INDEX IF EXISTS public.ix_events_creator_id;
DROP INDEX IF EXISTS public.ix_events_creator_gym;
DROP INDEX IF EXISTS public.ix_event_participations_status;
DROP INDEX IF EXISTS public.ix_event_participations_member_id;
DROP INDEX IF EXISTS public.ix_event_participations_id;
DROP INDEX IF EXISTS public.ix_event_participations_gym_id;
DROP INDEX IF EXISTS public.ix_event_participations_event_id;
DROP INDEX IF EXISTS public.ix_event_participation_gym_status;
DROP INDEX IF EXISTS public.ix_event_participation_event_member;
DROP INDEX IF EXISTS public.ix_device_tokens_user_id;
DROP INDEX IF EXISTS public.ix_class_session_start_time;
DROP INDEX IF EXISTS public.ix_class_session_id;
DROP INDEX IF EXISTS public.ix_class_participation_id;
DROP INDEX IF EXISTS public.ix_class_id;
DROP INDEX IF EXISTS public.ix_class_category_custom_id;
DROP INDEX IF EXISTS public.ix_chat_rooms_stream_channel_id;
DROP INDEX IF EXISTS public.ix_chat_rooms_is_direct;
DROP INDEX IF EXISTS public.ix_chat_rooms_id;
DROP INDEX IF EXISTS public.ix_chat_rooms_event_id_type;
DROP INDEX IF EXISTS public.ix_chat_rooms_event_id;
DROP INDEX IF EXISTS public.ix_chat_members_user_id_room_id;
DROP INDEX IF EXISTS public.ix_chat_members_id;
DROP INDEX IF EXISTS public.ix_chat_members_auth0_user_id;
DROP INDEX IF EXISTS public.idx_device_token;
DROP INDEX IF EXISTS auth.users_is_anonymous_idx;
DROP INDEX IF EXISTS auth.users_instance_id_idx;
DROP INDEX IF EXISTS auth.users_instance_id_email_idx;
DROP INDEX IF EXISTS auth.users_email_partial_key;
DROP INDEX IF EXISTS auth.user_id_created_at_idx;
DROP INDEX IF EXISTS auth.unique_phone_factor_per_user;
DROP INDEX IF EXISTS auth.sso_providers_resource_id_idx;
DROP INDEX IF EXISTS auth.sso_domains_sso_provider_id_idx;
DROP INDEX IF EXISTS auth.sso_domains_domain_idx;
DROP INDEX IF EXISTS auth.sessions_user_id_idx;
DROP INDEX IF EXISTS auth.sessions_not_after_idx;
DROP INDEX IF EXISTS auth.saml_relay_states_sso_provider_id_idx;
DROP INDEX IF EXISTS auth.saml_relay_states_for_email_idx;
DROP INDEX IF EXISTS auth.saml_relay_states_created_at_idx;
DROP INDEX IF EXISTS auth.saml_providers_sso_provider_id_idx;
DROP INDEX IF EXISTS auth.refresh_tokens_updated_at_idx;
DROP INDEX IF EXISTS auth.refresh_tokens_session_id_revoked_idx;
DROP INDEX IF EXISTS auth.refresh_tokens_parent_idx;
DROP INDEX IF EXISTS auth.refresh_tokens_instance_id_user_id_idx;
DROP INDEX IF EXISTS auth.refresh_tokens_instance_id_idx;
DROP INDEX IF EXISTS auth.recovery_token_idx;
DROP INDEX IF EXISTS auth.reauthentication_token_idx;
DROP INDEX IF EXISTS auth.one_time_tokens_user_id_token_type_key;
DROP INDEX IF EXISTS auth.one_time_tokens_token_hash_hash_idx;
DROP INDEX IF EXISTS auth.one_time_tokens_relates_to_hash_idx;
DROP INDEX IF EXISTS auth.mfa_factors_user_id_idx;
DROP INDEX IF EXISTS auth.mfa_factors_user_friendly_name_unique;
DROP INDEX IF EXISTS auth.mfa_challenge_created_at_idx;
DROP INDEX IF EXISTS auth.idx_user_id_auth_method;
DROP INDEX IF EXISTS auth.idx_auth_code;
DROP INDEX IF EXISTS auth.identities_user_id_idx;
DROP INDEX IF EXISTS auth.identities_email_idx;
DROP INDEX IF EXISTS auth.flow_state_created_at_idx;
DROP INDEX IF EXISTS auth.factor_id_created_at_idx;
DROP INDEX IF EXISTS auth.email_change_token_new_idx;
DROP INDEX IF EXISTS auth.email_change_token_current_idx;
DROP INDEX IF EXISTS auth.confirmation_token_idx;
DROP INDEX IF EXISTS auth.audit_logs_instance_id_idx;
ALTER TABLE IF EXISTS ONLY storage.s3_multipart_uploads DROP CONSTRAINT IF EXISTS s3_multipart_uploads_pkey;
ALTER TABLE IF EXISTS ONLY storage.s3_multipart_uploads_parts DROP CONSTRAINT IF EXISTS s3_multipart_uploads_parts_pkey;
ALTER TABLE IF EXISTS ONLY storage.objects DROP CONSTRAINT IF EXISTS objects_pkey;
ALTER TABLE IF EXISTS ONLY storage.migrations DROP CONSTRAINT IF EXISTS migrations_pkey;
ALTER TABLE IF EXISTS ONLY storage.migrations DROP CONSTRAINT IF EXISTS migrations_name_key;
ALTER TABLE IF EXISTS ONLY storage.buckets DROP CONSTRAINT IF EXISTS buckets_pkey;
ALTER TABLE IF EXISTS ONLY realtime.schema_migrations DROP CONSTRAINT IF EXISTS schema_migrations_pkey;
ALTER TABLE IF EXISTS ONLY realtime.subscription DROP CONSTRAINT IF EXISTS pk_subscription;
ALTER TABLE IF EXISTS ONLY realtime.messages DROP CONSTRAINT IF EXISTS messages_pkey;
ALTER TABLE IF EXISTS ONLY public."user" DROP CONSTRAINT IF EXISTS user_pkey;
ALTER TABLE IF EXISTS ONLY public.user_gyms DROP CONSTRAINT IF EXISTS user_gyms_pkey;
ALTER TABLE IF EXISTS ONLY public.user_gyms DROP CONSTRAINT IF EXISTS uq_user_gym;
ALTER TABLE IF EXISTS ONLY public.device_tokens DROP CONSTRAINT IF EXISTS uq_user_device_token;
ALTER TABLE IF EXISTS ONLY public.gym_special_hours DROP CONSTRAINT IF EXISTS uq_gym_special_hours_gym_date;
ALTER TABLE IF EXISTS ONLY public.trainermemberrelationship DROP CONSTRAINT IF EXISTS trainermemberrelationship_pkey;
ALTER TABLE IF EXISTS ONLY public.gyms DROP CONSTRAINT IF EXISTS gyms_pkey;
ALTER TABLE IF EXISTS ONLY public.gym_special_hours DROP CONSTRAINT IF EXISTS gym_special_hours_pkey;
ALTER TABLE IF EXISTS ONLY public.gym_hours DROP CONSTRAINT IF EXISTS gym_hours_pkey;
ALTER TABLE IF EXISTS ONLY public.events DROP CONSTRAINT IF EXISTS events_pkey;
ALTER TABLE IF EXISTS ONLY public.event_participations DROP CONSTRAINT IF EXISTS event_participations_pkey;
ALTER TABLE IF EXISTS ONLY public.device_tokens DROP CONSTRAINT IF EXISTS device_tokens_pkey;
ALTER TABLE IF EXISTS ONLY public.class_session DROP CONSTRAINT IF EXISTS class_session_pkey;
ALTER TABLE IF EXISTS ONLY public.class DROP CONSTRAINT IF EXISTS class_pkey;
ALTER TABLE IF EXISTS ONLY public.class_participation DROP CONSTRAINT IF EXISTS class_participation_pkey;
ALTER TABLE IF EXISTS ONLY public.class_category_custom DROP CONSTRAINT IF EXISTS class_category_custom_pkey;
ALTER TABLE IF EXISTS ONLY public.chat_rooms DROP CONSTRAINT IF EXISTS chat_rooms_pkey;
ALTER TABLE IF EXISTS ONLY public.chat_members DROP CONSTRAINT IF EXISTS chat_members_pkey;
ALTER TABLE IF EXISTS ONLY public.alembic_version DROP CONSTRAINT IF EXISTS alembic_version_pkc;
ALTER TABLE IF EXISTS ONLY auth.users DROP CONSTRAINT IF EXISTS users_pkey;
ALTER TABLE IF EXISTS ONLY auth.users DROP CONSTRAINT IF EXISTS users_phone_key;
ALTER TABLE IF EXISTS ONLY auth.sso_providers DROP CONSTRAINT IF EXISTS sso_providers_pkey;
ALTER TABLE IF EXISTS ONLY auth.sso_domains DROP CONSTRAINT IF EXISTS sso_domains_pkey;
ALTER TABLE IF EXISTS ONLY auth.sessions DROP CONSTRAINT IF EXISTS sessions_pkey;
ALTER TABLE IF EXISTS ONLY auth.schema_migrations DROP CONSTRAINT IF EXISTS schema_migrations_pkey;
ALTER TABLE IF EXISTS ONLY auth.saml_relay_states DROP CONSTRAINT IF EXISTS saml_relay_states_pkey;
ALTER TABLE IF EXISTS ONLY auth.saml_providers DROP CONSTRAINT IF EXISTS saml_providers_pkey;
ALTER TABLE IF EXISTS ONLY auth.saml_providers DROP CONSTRAINT IF EXISTS saml_providers_entity_id_key;
ALTER TABLE IF EXISTS ONLY auth.refresh_tokens DROP CONSTRAINT IF EXISTS refresh_tokens_token_unique;
ALTER TABLE IF EXISTS ONLY auth.refresh_tokens DROP CONSTRAINT IF EXISTS refresh_tokens_pkey;
ALTER TABLE IF EXISTS ONLY auth.one_time_tokens DROP CONSTRAINT IF EXISTS one_time_tokens_pkey;
ALTER TABLE IF EXISTS ONLY auth.mfa_factors DROP CONSTRAINT IF EXISTS mfa_factors_pkey;
ALTER TABLE IF EXISTS ONLY auth.mfa_factors DROP CONSTRAINT IF EXISTS mfa_factors_last_challenged_at_key;
ALTER TABLE IF EXISTS ONLY auth.mfa_challenges DROP CONSTRAINT IF EXISTS mfa_challenges_pkey;
ALTER TABLE IF EXISTS ONLY auth.mfa_amr_claims DROP CONSTRAINT IF EXISTS mfa_amr_claims_session_id_authentication_method_pkey;
ALTER TABLE IF EXISTS ONLY auth.instances DROP CONSTRAINT IF EXISTS instances_pkey;
ALTER TABLE IF EXISTS ONLY auth.identities DROP CONSTRAINT IF EXISTS identities_provider_id_provider_unique;
ALTER TABLE IF EXISTS ONLY auth.identities DROP CONSTRAINT IF EXISTS identities_pkey;
ALTER TABLE IF EXISTS ONLY auth.flow_state DROP CONSTRAINT IF EXISTS flow_state_pkey;
ALTER TABLE IF EXISTS ONLY auth.audit_log_entries DROP CONSTRAINT IF EXISTS audit_log_entries_pkey;
ALTER TABLE IF EXISTS ONLY auth.mfa_amr_claims DROP CONSTRAINT IF EXISTS amr_id_pk;
ALTER TABLE IF EXISTS public.user_gyms ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public."user" ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.trainermemberrelationship ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.gyms ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.gym_special_hours ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.gym_hours ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.events ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.event_participations ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.class_session ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.class_participation ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.class_category_custom ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.class ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.chat_rooms ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.chat_members ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS auth.refresh_tokens ALTER COLUMN id DROP DEFAULT;
DROP VIEW IF EXISTS vault.decrypted_secrets;
DROP TABLE IF EXISTS storage.s3_multipart_uploads_parts;
DROP TABLE IF EXISTS storage.s3_multipart_uploads;
DROP TABLE IF EXISTS storage.objects;
DROP TABLE IF EXISTS storage.migrations;
DROP TABLE IF EXISTS storage.buckets;
DROP TABLE IF EXISTS realtime.subscription;
DROP TABLE IF EXISTS realtime.schema_migrations;
DROP TABLE IF EXISTS realtime.messages;
DROP SEQUENCE IF EXISTS public.user_id_seq;
DROP SEQUENCE IF EXISTS public.user_gyms_id_seq;
DROP TABLE IF EXISTS public.user_gyms;
DROP TABLE IF EXISTS public."user";
DROP SEQUENCE IF EXISTS public.trainermemberrelationship_id_seq;
DROP TABLE IF EXISTS public.trainermemberrelationship;
DROP SEQUENCE IF EXISTS public.gyms_id_seq;
DROP TABLE IF EXISTS public.gyms;
DROP SEQUENCE IF EXISTS public.gym_special_hours_id_seq;
DROP TABLE IF EXISTS public.gym_special_hours;
DROP SEQUENCE IF EXISTS public.gym_hours_id_seq;
DROP TABLE IF EXISTS public.gym_hours;
DROP SEQUENCE IF EXISTS public.events_id_seq;
DROP TABLE IF EXISTS public.events;
DROP SEQUENCE IF EXISTS public.event_participations_id_seq;
DROP TABLE IF EXISTS public.event_participations;
DROP TABLE IF EXISTS public.device_tokens;
DROP SEQUENCE IF EXISTS public.class_session_id_seq;
DROP TABLE IF EXISTS public.class_session;
DROP SEQUENCE IF EXISTS public.class_participation_id_seq;
DROP TABLE IF EXISTS public.class_participation;
DROP SEQUENCE IF EXISTS public.class_id_seq;
DROP SEQUENCE IF EXISTS public.class_category_custom_id_seq;
DROP TABLE IF EXISTS public.class_category_custom;
DROP TABLE IF EXISTS public.class;
DROP SEQUENCE IF EXISTS public.chat_rooms_id_seq;
DROP TABLE IF EXISTS public.chat_rooms;
DROP SEQUENCE IF EXISTS public.chat_members_id_seq;
DROP TABLE IF EXISTS public.chat_members;
DROP TABLE IF EXISTS public.alembic_version;
DROP TABLE IF EXISTS auth.users;
DROP TABLE IF EXISTS auth.sso_providers;
DROP TABLE IF EXISTS auth.sso_domains;
DROP TABLE IF EXISTS auth.sessions;
DROP TABLE IF EXISTS auth.schema_migrations;
DROP TABLE IF EXISTS auth.saml_relay_states;
DROP TABLE IF EXISTS auth.saml_providers;
DROP SEQUENCE IF EXISTS auth.refresh_tokens_id_seq;
DROP TABLE IF EXISTS auth.refresh_tokens;
DROP TABLE IF EXISTS auth.one_time_tokens;
DROP TABLE IF EXISTS auth.mfa_factors;
DROP TABLE IF EXISTS auth.mfa_challenges;
DROP TABLE IF EXISTS auth.mfa_amr_claims;
DROP TABLE IF EXISTS auth.instances;
DROP TABLE IF EXISTS auth.identities;
DROP TABLE IF EXISTS auth.flow_state;
DROP TABLE IF EXISTS auth.audit_log_entries;
DROP FUNCTION IF EXISTS vault.secrets_encrypt_secret_secret();
DROP FUNCTION IF EXISTS storage.update_updated_at_column();
DROP FUNCTION IF EXISTS storage.search(prefix text, bucketname text, limits integer, levels integer, offsets integer, search text, sortcolumn text, sortorder text);
DROP FUNCTION IF EXISTS storage.operation();
DROP FUNCTION IF EXISTS storage.list_objects_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer, start_after text, next_token text);
DROP FUNCTION IF EXISTS storage.list_multipart_uploads_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer, next_key_token text, next_upload_token text);
DROP FUNCTION IF EXISTS storage.get_size_by_bucket();
DROP FUNCTION IF EXISTS storage.foldername(name text);
DROP FUNCTION IF EXISTS storage.filename(name text);
DROP FUNCTION IF EXISTS storage.extension(name text);
DROP FUNCTION IF EXISTS storage.can_insert_object(bucketid text, name text, owner uuid, metadata jsonb);
DROP FUNCTION IF EXISTS realtime.topic();
DROP FUNCTION IF EXISTS realtime.to_regrole(role_name text);
DROP FUNCTION IF EXISTS realtime.subscription_check_filters();
DROP FUNCTION IF EXISTS realtime.send(payload jsonb, event text, topic text, private boolean);
DROP FUNCTION IF EXISTS realtime.quote_wal2json(entity regclass);
DROP FUNCTION IF EXISTS realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer);
DROP FUNCTION IF EXISTS realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]);
DROP FUNCTION IF EXISTS realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text);
DROP FUNCTION IF EXISTS realtime."cast"(val text, type_ regtype);
DROP FUNCTION IF EXISTS realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]);
DROP FUNCTION IF EXISTS realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text);
DROP FUNCTION IF EXISTS realtime.apply_rls(wal jsonb, max_record_bytes integer);
DROP FUNCTION IF EXISTS pgbouncer.get_auth(p_usename text);
DROP FUNCTION IF EXISTS extensions.set_graphql_placeholder();
DROP FUNCTION IF EXISTS extensions.pgrst_drop_watch();
DROP FUNCTION IF EXISTS extensions.pgrst_ddl_watch();
DROP FUNCTION IF EXISTS extensions.grant_pg_net_access();
DROP FUNCTION IF EXISTS extensions.grant_pg_graphql_access();
DROP FUNCTION IF EXISTS extensions.grant_pg_cron_access();
DROP FUNCTION IF EXISTS auth.uid();
DROP FUNCTION IF EXISTS auth.role();
DROP FUNCTION IF EXISTS auth.jwt();
DROP FUNCTION IF EXISTS auth.email();
DROP TYPE IF EXISTS realtime.wal_rls;
DROP TYPE IF EXISTS realtime.wal_column;
DROP TYPE IF EXISTS realtime.user_defined_filter;
DROP TYPE IF EXISTS realtime.equality_op;
DROP TYPE IF EXISTS realtime.action;
DROP TYPE IF EXISTS public.userrole;
DROP TYPE IF EXISTS public.relationshipstatus;
DROP TYPE IF EXISTS public.gymroletype;
DROP TYPE IF EXISTS public.eventstatus;
DROP TYPE IF EXISTS public.eventparticipationstatus;
DROP TYPE IF EXISTS public.classsessionstatus;
DROP TYPE IF EXISTS public.classparticipationstatus;
DROP TYPE IF EXISTS public."classdifficultyLevel";
DROP TYPE IF EXISTS public.classcategory;
DROP TYPE IF EXISTS auth.one_time_token_type;
DROP TYPE IF EXISTS auth.factor_type;
DROP TYPE IF EXISTS auth.factor_status;
DROP TYPE IF EXISTS auth.code_challenge_method;
DROP TYPE IF EXISTS auth.aal_level;
DROP EXTENSION IF EXISTS "uuid-ossp";
DROP EXTENSION IF EXISTS supabase_vault;
DROP EXTENSION IF EXISTS pgjwt;
DROP EXTENSION IF EXISTS pgcrypto;
DROP EXTENSION IF EXISTS pg_stat_statements;
DROP EXTENSION IF EXISTS pg_graphql;
DROP SCHEMA IF EXISTS vault;
DROP SCHEMA IF EXISTS storage;
DROP SCHEMA IF EXISTS realtime;
DROP EXTENSION IF EXISTS pgsodium;
DROP SCHEMA IF EXISTS pgsodium;
DROP SCHEMA IF EXISTS pgbouncer;
DROP SCHEMA IF EXISTS graphql_public;
DROP SCHEMA IF EXISTS graphql;
DROP SCHEMA IF EXISTS extensions;
DROP SCHEMA IF EXISTS auth;
--
-- Name: auth; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA auth;


--
-- Name: extensions; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA extensions;


--
-- Name: graphql; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA graphql;


--
-- Name: graphql_public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA graphql_public;


--
-- Name: pgbouncer; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA pgbouncer;


--
-- Name: pgsodium; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA pgsodium;


--
-- Name: pgsodium; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgsodium WITH SCHEMA pgsodium;


--
-- Name: EXTENSION pgsodium; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgsodium IS 'Pgsodium is a modern cryptography library for Postgres.';


--
-- Name: realtime; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA realtime;


--
-- Name: storage; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA storage;


--
-- Name: vault; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA vault;


--
-- Name: pg_graphql; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_graphql WITH SCHEMA graphql;


--
-- Name: EXTENSION pg_graphql; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_graphql IS 'pg_graphql: GraphQL support';


--
-- Name: pg_stat_statements; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA extensions;


--
-- Name: EXTENSION pg_stat_statements; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_stat_statements IS 'track planning and execution statistics of all SQL statements executed';


--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: pgjwt; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgjwt WITH SCHEMA extensions;


--
-- Name: EXTENSION pgjwt; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgjwt IS 'JSON Web Token API for Postgresql';


--
-- Name: supabase_vault; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS supabase_vault WITH SCHEMA vault;


--
-- Name: EXTENSION supabase_vault; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION supabase_vault IS 'Supabase Vault Extension';


--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA extensions;


--
-- Name: EXTENSION "uuid-ossp"; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';


--
-- Name: aal_level; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.aal_level AS ENUM (
    'aal1',
    'aal2',
    'aal3'
);


--
-- Name: code_challenge_method; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.code_challenge_method AS ENUM (
    's256',
    'plain'
);


--
-- Name: factor_status; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.factor_status AS ENUM (
    'unverified',
    'verified'
);


--
-- Name: factor_type; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.factor_type AS ENUM (
    'totp',
    'webauthn',
    'phone'
);


--
-- Name: one_time_token_type; Type: TYPE; Schema: auth; Owner: -
--

CREATE TYPE auth.one_time_token_type AS ENUM (
    'confirmation_token',
    'reauthentication_token',
    'recovery_token',
    'email_change_token_new',
    'email_change_token_current',
    'phone_change_token'
);


--
-- Name: classcategory; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.classcategory AS ENUM (
    'CARDIO',
    'STRENGTH',
    'FLEXIBILITY',
    'HIIT',
    'YOGA',
    'PILATES',
    'FUNCTIONAL',
    'OTHER'
);


--
-- Name: classdifficultyLevel; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."classdifficultyLevel" AS ENUM (
    'BEGINNER',
    'INTERMEDIATE',
    'ADVANCED'
);


--
-- Name: classparticipationstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.classparticipationstatus AS ENUM (
    'REGISTERED',
    'ATTENDED',
    'CANCELLED',
    'NO_SHOW'
);


--
-- Name: classsessionstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.classsessionstatus AS ENUM (
    'SCHEDULED',
    'IN_PROGRESS',
    'COMPLETED',
    'CANCELLED'
);


--
-- Name: eventparticipationstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.eventparticipationstatus AS ENUM (
    'REGISTERED',
    'CANCELLED',
    'WAITING_LIST'
);


--
-- Name: eventstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.eventstatus AS ENUM (
    'SCHEDULED',
    'CANCELLED',
    'COMPLETED'
);


--
-- Name: gymroletype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.gymroletype AS ENUM (
    'OWNER',
    'ADMIN',
    'TRAINER',
    'MEMBER'
);


--
-- Name: relationshipstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.relationshipstatus AS ENUM (
    'ACTIVE',
    'PAUSED',
    'TERMINATED',
    'PENDING'
);


--
-- Name: userrole; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.userrole AS ENUM (
    'SUPER_ADMIN',
    'ADMIN',
    'TRAINER',
    'MEMBER'
);


--
-- Name: action; Type: TYPE; Schema: realtime; Owner: -
--

CREATE TYPE realtime.action AS ENUM (
    'INSERT',
    'UPDATE',
    'DELETE',
    'TRUNCATE',
    'ERROR'
);


--
-- Name: equality_op; Type: TYPE; Schema: realtime; Owner: -
--

CREATE TYPE realtime.equality_op AS ENUM (
    'eq',
    'neq',
    'lt',
    'lte',
    'gt',
    'gte',
    'in'
);


--
-- Name: user_defined_filter; Type: TYPE; Schema: realtime; Owner: -
--

CREATE TYPE realtime.user_defined_filter AS (
	column_name text,
	op realtime.equality_op,
	value text
);


--
-- Name: wal_column; Type: TYPE; Schema: realtime; Owner: -
--

CREATE TYPE realtime.wal_column AS (
	name text,
	type_name text,
	type_oid oid,
	value jsonb,
	is_pkey boolean,
	is_selectable boolean
);


--
-- Name: wal_rls; Type: TYPE; Schema: realtime; Owner: -
--

CREATE TYPE realtime.wal_rls AS (
	wal jsonb,
	is_rls_enabled boolean,
	subscription_ids uuid[],
	errors text[]
);


--
-- Name: email(); Type: FUNCTION; Schema: auth; Owner: -
--

CREATE FUNCTION auth.email() RETURNS text
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.email', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'email')
  )::text
$$;


--
-- Name: FUNCTION email(); Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON FUNCTION auth.email() IS 'Deprecated. Use auth.jwt() -> ''email'' instead.';


--
-- Name: jwt(); Type: FUNCTION; Schema: auth; Owner: -
--

CREATE FUNCTION auth.jwt() RETURNS jsonb
    LANGUAGE sql STABLE
    AS $$
  select 
    coalesce(
        nullif(current_setting('request.jwt.claim', true), ''),
        nullif(current_setting('request.jwt.claims', true), '')
    )::jsonb
$$;


--
-- Name: role(); Type: FUNCTION; Schema: auth; Owner: -
--

CREATE FUNCTION auth.role() RETURNS text
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.role', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role')
  )::text
$$;


--
-- Name: FUNCTION role(); Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON FUNCTION auth.role() IS 'Deprecated. Use auth.jwt() -> ''role'' instead.';


--
-- Name: uid(); Type: FUNCTION; Schema: auth; Owner: -
--

CREATE FUNCTION auth.uid() RETURNS uuid
    LANGUAGE sql STABLE
    AS $$
  select 
  coalesce(
    nullif(current_setting('request.jwt.claim.sub', true), ''),
    (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
  )::uuid
$$;


--
-- Name: FUNCTION uid(); Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON FUNCTION auth.uid() IS 'Deprecated. Use auth.jwt() -> ''sub'' instead.';


--
-- Name: grant_pg_cron_access(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.grant_pg_cron_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF EXISTS (
    SELECT
    FROM pg_event_trigger_ddl_commands() AS ev
    JOIN pg_extension AS ext
    ON ev.objid = ext.oid
    WHERE ext.extname = 'pg_cron'
  )
  THEN
    grant usage on schema cron to postgres with grant option;

    alter default privileges in schema cron grant all on tables to postgres with grant option;
    alter default privileges in schema cron grant all on functions to postgres with grant option;
    alter default privileges in schema cron grant all on sequences to postgres with grant option;

    alter default privileges for user supabase_admin in schema cron grant all
        on sequences to postgres with grant option;
    alter default privileges for user supabase_admin in schema cron grant all
        on tables to postgres with grant option;
    alter default privileges for user supabase_admin in schema cron grant all
        on functions to postgres with grant option;

    grant all privileges on all tables in schema cron to postgres with grant option;
    revoke all on table cron.job from postgres;
    grant select on table cron.job to postgres with grant option;
  END IF;
END;
$$;


--
-- Name: FUNCTION grant_pg_cron_access(); Type: COMMENT; Schema: extensions; Owner: -
--

COMMENT ON FUNCTION extensions.grant_pg_cron_access() IS 'Grants access to pg_cron';


--
-- Name: grant_pg_graphql_access(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.grant_pg_graphql_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $_$
DECLARE
    func_is_graphql_resolve bool;
BEGIN
    func_is_graphql_resolve = (
        SELECT n.proname = 'resolve'
        FROM pg_event_trigger_ddl_commands() AS ev
        LEFT JOIN pg_catalog.pg_proc AS n
        ON ev.objid = n.oid
    );

    IF func_is_graphql_resolve
    THEN
        -- Update public wrapper to pass all arguments through to the pg_graphql resolve func
        DROP FUNCTION IF EXISTS graphql_public.graphql;
        create or replace function graphql_public.graphql(
            "operationName" text default null,
            query text default null,
            variables jsonb default null,
            extensions jsonb default null
        )
            returns jsonb
            language sql
        as $$
            select graphql.resolve(
                query := query,
                variables := coalesce(variables, '{}'),
                "operationName" := "operationName",
                extensions := extensions
            );
        $$;

        -- This hook executes when `graphql.resolve` is created. That is not necessarily the last
        -- function in the extension so we need to grant permissions on existing entities AND
        -- update default permissions to any others that are created after `graphql.resolve`
        grant usage on schema graphql to postgres, anon, authenticated, service_role;
        grant select on all tables in schema graphql to postgres, anon, authenticated, service_role;
        grant execute on all functions in schema graphql to postgres, anon, authenticated, service_role;
        grant all on all sequences in schema graphql to postgres, anon, authenticated, service_role;
        alter default privileges in schema graphql grant all on tables to postgres, anon, authenticated, service_role;
        alter default privileges in schema graphql grant all on functions to postgres, anon, authenticated, service_role;
        alter default privileges in schema graphql grant all on sequences to postgres, anon, authenticated, service_role;

        -- Allow postgres role to allow granting usage on graphql and graphql_public schemas to custom roles
        grant usage on schema graphql_public to postgres with grant option;
        grant usage on schema graphql to postgres with grant option;
    END IF;

END;
$_$;


--
-- Name: FUNCTION grant_pg_graphql_access(); Type: COMMENT; Schema: extensions; Owner: -
--

COMMENT ON FUNCTION extensions.grant_pg_graphql_access() IS 'Grants access to pg_graphql';


--
-- Name: grant_pg_net_access(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.grant_pg_net_access() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_event_trigger_ddl_commands() AS ev
    JOIN pg_extension AS ext
    ON ev.objid = ext.oid
    WHERE ext.extname = 'pg_net'
  )
  THEN
    IF NOT EXISTS (
      SELECT 1
      FROM pg_roles
      WHERE rolname = 'supabase_functions_admin'
    )
    THEN
      CREATE USER supabase_functions_admin NOINHERIT CREATEROLE LOGIN NOREPLICATION;
    END IF;

    GRANT USAGE ON SCHEMA net TO supabase_functions_admin, postgres, anon, authenticated, service_role;

    IF EXISTS (
      SELECT FROM pg_extension
      WHERE extname = 'pg_net'
      -- all versions in use on existing projects as of 2025-02-20
      -- version 0.12.0 onwards don't need these applied
      AND extversion IN ('0.2', '0.6', '0.7', '0.7.1', '0.8', '0.10.0', '0.11.0')
    ) THEN
      ALTER function net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) SECURITY DEFINER;
      ALTER function net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) SECURITY DEFINER;

      ALTER function net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) SET search_path = net;
      ALTER function net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) SET search_path = net;

      REVOKE ALL ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;
      REVOKE ALL ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) FROM PUBLIC;

      GRANT EXECUTE ON FUNCTION net.http_get(url text, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin, postgres, anon, authenticated, service_role;
      GRANT EXECUTE ON FUNCTION net.http_post(url text, body jsonb, params jsonb, headers jsonb, timeout_milliseconds integer) TO supabase_functions_admin, postgres, anon, authenticated, service_role;
    END IF;
  END IF;
END;
$$;


--
-- Name: FUNCTION grant_pg_net_access(); Type: COMMENT; Schema: extensions; Owner: -
--

COMMENT ON FUNCTION extensions.grant_pg_net_access() IS 'Grants access to pg_net';


--
-- Name: pgrst_ddl_watch(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.pgrst_ddl_watch() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  cmd record;
BEGIN
  FOR cmd IN SELECT * FROM pg_event_trigger_ddl_commands()
  LOOP
    IF cmd.command_tag IN (
      'CREATE SCHEMA', 'ALTER SCHEMA'
    , 'CREATE TABLE', 'CREATE TABLE AS', 'SELECT INTO', 'ALTER TABLE'
    , 'CREATE FOREIGN TABLE', 'ALTER FOREIGN TABLE'
    , 'CREATE VIEW', 'ALTER VIEW'
    , 'CREATE MATERIALIZED VIEW', 'ALTER MATERIALIZED VIEW'
    , 'CREATE FUNCTION', 'ALTER FUNCTION'
    , 'CREATE TRIGGER'
    , 'CREATE TYPE', 'ALTER TYPE'
    , 'CREATE RULE'
    , 'COMMENT'
    )
    -- don't notify in case of CREATE TEMP table or other objects created on pg_temp
    AND cmd.schema_name is distinct from 'pg_temp'
    THEN
      NOTIFY pgrst, 'reload schema';
    END IF;
  END LOOP;
END; $$;


--
-- Name: pgrst_drop_watch(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.pgrst_drop_watch() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  obj record;
BEGIN
  FOR obj IN SELECT * FROM pg_event_trigger_dropped_objects()
  LOOP
    IF obj.object_type IN (
      'schema'
    , 'table'
    , 'foreign table'
    , 'view'
    , 'materialized view'
    , 'function'
    , 'trigger'
    , 'type'
    , 'rule'
    )
    AND obj.is_temporary IS false -- no pg_temp objects
    THEN
      NOTIFY pgrst, 'reload schema';
    END IF;
  END LOOP;
END; $$;


--
-- Name: set_graphql_placeholder(); Type: FUNCTION; Schema: extensions; Owner: -
--

CREATE FUNCTION extensions.set_graphql_placeholder() RETURNS event_trigger
    LANGUAGE plpgsql
    AS $_$
    DECLARE
    graphql_is_dropped bool;
    BEGIN
    graphql_is_dropped = (
        SELECT ev.schema_name = 'graphql_public'
        FROM pg_event_trigger_dropped_objects() AS ev
        WHERE ev.schema_name = 'graphql_public'
    );

    IF graphql_is_dropped
    THEN
        create or replace function graphql_public.graphql(
            "operationName" text default null,
            query text default null,
            variables jsonb default null,
            extensions jsonb default null
        )
            returns jsonb
            language plpgsql
        as $$
            DECLARE
                server_version float;
            BEGIN
                server_version = (SELECT (SPLIT_PART((select version()), ' ', 2))::float);

                IF server_version >= 14 THEN
                    RETURN jsonb_build_object(
                        'errors', jsonb_build_array(
                            jsonb_build_object(
                                'message', 'pg_graphql extension is not enabled.'
                            )
                        )
                    );
                ELSE
                    RETURN jsonb_build_object(
                        'errors', jsonb_build_array(
                            jsonb_build_object(
                                'message', 'pg_graphql is only available on projects running Postgres 14 onwards.'
                            )
                        )
                    );
                END IF;
            END;
        $$;
    END IF;

    END;
$_$;


--
-- Name: FUNCTION set_graphql_placeholder(); Type: COMMENT; Schema: extensions; Owner: -
--

COMMENT ON FUNCTION extensions.set_graphql_placeholder() IS 'Reintroduces placeholder function for graphql_public.graphql';


--
-- Name: get_auth(text); Type: FUNCTION; Schema: pgbouncer; Owner: -
--

CREATE FUNCTION pgbouncer.get_auth(p_usename text) RETURNS TABLE(username text, password text)
    LANGUAGE plpgsql SECURITY DEFINER
    AS $$
BEGIN
    RAISE WARNING 'PgBouncer auth request: %', p_usename;

    RETURN QUERY
    SELECT usename::TEXT, passwd::TEXT FROM pg_catalog.pg_shadow
    WHERE usename = p_usename;
END;
$$;


--
-- Name: apply_rls(jsonb, integer); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.apply_rls(wal jsonb, max_record_bytes integer DEFAULT (1024 * 1024)) RETURNS SETOF realtime.wal_rls
    LANGUAGE plpgsql
    AS $$
declare
-- Regclass of the table e.g. public.notes
entity_ regclass = (quote_ident(wal ->> 'schema') || '.' || quote_ident(wal ->> 'table'))::regclass;

-- I, U, D, T: insert, update ...
action realtime.action = (
    case wal ->> 'action'
        when 'I' then 'INSERT'
        when 'U' then 'UPDATE'
        when 'D' then 'DELETE'
        else 'ERROR'
    end
);

-- Is row level security enabled for the table
is_rls_enabled bool = relrowsecurity from pg_class where oid = entity_;

subscriptions realtime.subscription[] = array_agg(subs)
    from
        realtime.subscription subs
    where
        subs.entity = entity_;

-- Subscription vars
roles regrole[] = array_agg(distinct us.claims_role::text)
    from
        unnest(subscriptions) us;

working_role regrole;
claimed_role regrole;
claims jsonb;

subscription_id uuid;
subscription_has_access bool;
visible_to_subscription_ids uuid[] = '{}';

-- structured info for wal's columns
columns realtime.wal_column[];
-- previous identity values for update/delete
old_columns realtime.wal_column[];

error_record_exceeds_max_size boolean = octet_length(wal::text) > max_record_bytes;

-- Primary jsonb output for record
output jsonb;

begin
perform set_config('role', null, true);

columns =
    array_agg(
        (
            x->>'name',
            x->>'type',
            x->>'typeoid',
            realtime.cast(
                (x->'value') #>> '{}',
                coalesce(
                    (x->>'typeoid')::regtype, -- null when wal2json version <= 2.4
                    (x->>'type')::regtype
                )
            ),
            (pks ->> 'name') is not null,
            true
        )::realtime.wal_column
    )
    from
        jsonb_array_elements(wal -> 'columns') x
        left join jsonb_array_elements(wal -> 'pk') pks
            on (x ->> 'name') = (pks ->> 'name');

old_columns =
    array_agg(
        (
            x->>'name',
            x->>'type',
            x->>'typeoid',
            realtime.cast(
                (x->'value') #>> '{}',
                coalesce(
                    (x->>'typeoid')::regtype, -- null when wal2json version <= 2.4
                    (x->>'type')::regtype
                )
            ),
            (pks ->> 'name') is not null,
            true
        )::realtime.wal_column
    )
    from
        jsonb_array_elements(wal -> 'identity') x
        left join jsonb_array_elements(wal -> 'pk') pks
            on (x ->> 'name') = (pks ->> 'name');

for working_role in select * from unnest(roles) loop

    -- Update `is_selectable` for columns and old_columns
    columns =
        array_agg(
            (
                c.name,
                c.type_name,
                c.type_oid,
                c.value,
                c.is_pkey,
                pg_catalog.has_column_privilege(working_role, entity_, c.name, 'SELECT')
            )::realtime.wal_column
        )
        from
            unnest(columns) c;

    old_columns =
            array_agg(
                (
                    c.name,
                    c.type_name,
                    c.type_oid,
                    c.value,
                    c.is_pkey,
                    pg_catalog.has_column_privilege(working_role, entity_, c.name, 'SELECT')
                )::realtime.wal_column
            )
            from
                unnest(old_columns) c;

    if action <> 'DELETE' and count(1) = 0 from unnest(columns) c where c.is_pkey then
        return next (
            jsonb_build_object(
                'schema', wal ->> 'schema',
                'table', wal ->> 'table',
                'type', action
            ),
            is_rls_enabled,
            -- subscriptions is already filtered by entity
            (select array_agg(s.subscription_id) from unnest(subscriptions) as s where claims_role = working_role),
            array['Error 400: Bad Request, no primary key']
        )::realtime.wal_rls;

    -- The claims role does not have SELECT permission to the primary key of entity
    elsif action <> 'DELETE' and sum(c.is_selectable::int) <> count(1) from unnest(columns) c where c.is_pkey then
        return next (
            jsonb_build_object(
                'schema', wal ->> 'schema',
                'table', wal ->> 'table',
                'type', action
            ),
            is_rls_enabled,
            (select array_agg(s.subscription_id) from unnest(subscriptions) as s where claims_role = working_role),
            array['Error 401: Unauthorized']
        )::realtime.wal_rls;

    else
        output = jsonb_build_object(
            'schema', wal ->> 'schema',
            'table', wal ->> 'table',
            'type', action,
            'commit_timestamp', to_char(
                ((wal ->> 'timestamp')::timestamptz at time zone 'utc'),
                'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'
            ),
            'columns', (
                select
                    jsonb_agg(
                        jsonb_build_object(
                            'name', pa.attname,
                            'type', pt.typname
                        )
                        order by pa.attnum asc
                    )
                from
                    pg_attribute pa
                    join pg_type pt
                        on pa.atttypid = pt.oid
                where
                    attrelid = entity_
                    and attnum > 0
                    and pg_catalog.has_column_privilege(working_role, entity_, pa.attname, 'SELECT')
            )
        )
        -- Add "record" key for insert and update
        || case
            when action in ('INSERT', 'UPDATE') then
                jsonb_build_object(
                    'record',
                    (
                        select
                            jsonb_object_agg(
                                -- if unchanged toast, get column name and value from old record
                                coalesce((c).name, (oc).name),
                                case
                                    when (c).name is null then (oc).value
                                    else (c).value
                                end
                            )
                        from
                            unnest(columns) c
                            full outer join unnest(old_columns) oc
                                on (c).name = (oc).name
                        where
                            coalesce((c).is_selectable, (oc).is_selectable)
                            and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                    )
                )
            else '{}'::jsonb
        end
        -- Add "old_record" key for update and delete
        || case
            when action = 'UPDATE' then
                jsonb_build_object(
                        'old_record',
                        (
                            select jsonb_object_agg((c).name, (c).value)
                            from unnest(old_columns) c
                            where
                                (c).is_selectable
                                and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                        )
                    )
            when action = 'DELETE' then
                jsonb_build_object(
                    'old_record',
                    (
                        select jsonb_object_agg((c).name, (c).value)
                        from unnest(old_columns) c
                        where
                            (c).is_selectable
                            and ( not error_record_exceeds_max_size or (octet_length((c).value::text) <= 64))
                            and ( not is_rls_enabled or (c).is_pkey ) -- if RLS enabled, we can't secure deletes so filter to pkey
                    )
                )
            else '{}'::jsonb
        end;

        -- Create the prepared statement
        if is_rls_enabled and action <> 'DELETE' then
            if (select 1 from pg_prepared_statements where name = 'walrus_rls_stmt' limit 1) > 0 then
                deallocate walrus_rls_stmt;
            end if;
            execute realtime.build_prepared_statement_sql('walrus_rls_stmt', entity_, columns);
        end if;

        visible_to_subscription_ids = '{}';

        for subscription_id, claims in (
                select
                    subs.subscription_id,
                    subs.claims
                from
                    unnest(subscriptions) subs
                where
                    subs.entity = entity_
                    and subs.claims_role = working_role
                    and (
                        realtime.is_visible_through_filters(columns, subs.filters)
                        or (
                          action = 'DELETE'
                          and realtime.is_visible_through_filters(old_columns, subs.filters)
                        )
                    )
        ) loop

            if not is_rls_enabled or action = 'DELETE' then
                visible_to_subscription_ids = visible_to_subscription_ids || subscription_id;
            else
                -- Check if RLS allows the role to see the record
                perform
                    -- Trim leading and trailing quotes from working_role because set_config
                    -- doesn't recognize the role as valid if they are included
                    set_config('role', trim(both '"' from working_role::text), true),
                    set_config('request.jwt.claims', claims::text, true);

                execute 'execute walrus_rls_stmt' into subscription_has_access;

                if subscription_has_access then
                    visible_to_subscription_ids = visible_to_subscription_ids || subscription_id;
                end if;
            end if;
        end loop;

        perform set_config('role', null, true);

        return next (
            output,
            is_rls_enabled,
            visible_to_subscription_ids,
            case
                when error_record_exceeds_max_size then array['Error 413: Payload Too Large']
                else '{}'
            end
        )::realtime.wal_rls;

    end if;
end loop;

perform set_config('role', null, true);
end;
$$;


--
-- Name: broadcast_changes(text, text, text, text, text, record, record, text); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.broadcast_changes(topic_name text, event_name text, operation text, table_name text, table_schema text, new record, old record, level text DEFAULT 'ROW'::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    -- Declare a variable to hold the JSONB representation of the row
    row_data jsonb := '{}'::jsonb;
BEGIN
    IF level = 'STATEMENT' THEN
        RAISE EXCEPTION 'function can only be triggered for each row, not for each statement';
    END IF;
    -- Check the operation type and handle accordingly
    IF operation = 'INSERT' OR operation = 'UPDATE' OR operation = 'DELETE' THEN
        row_data := jsonb_build_object('old_record', OLD, 'record', NEW, 'operation', operation, 'table', table_name, 'schema', table_schema);
        PERFORM realtime.send (row_data, event_name, topic_name);
    ELSE
        RAISE EXCEPTION 'Unexpected operation type: %', operation;
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        RAISE EXCEPTION 'Failed to process the row: %', SQLERRM;
END;

$$;


--
-- Name: build_prepared_statement_sql(text, regclass, realtime.wal_column[]); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.build_prepared_statement_sql(prepared_statement_name text, entity regclass, columns realtime.wal_column[]) RETURNS text
    LANGUAGE sql
    AS $$
      /*
      Builds a sql string that, if executed, creates a prepared statement to
      tests retrive a row from *entity* by its primary key columns.
      Example
          select realtime.build_prepared_statement_sql('public.notes', '{"id"}'::text[], '{"bigint"}'::text[])
      */
          select
      'prepare ' || prepared_statement_name || ' as
          select
              exists(
                  select
                      1
                  from
                      ' || entity || '
                  where
                      ' || string_agg(quote_ident(pkc.name) || '=' || quote_nullable(pkc.value #>> '{}') , ' and ') || '
              )'
          from
              unnest(columns) pkc
          where
              pkc.is_pkey
          group by
              entity
      $$;


--
-- Name: cast(text, regtype); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime."cast"(val text, type_ regtype) RETURNS jsonb
    LANGUAGE plpgsql IMMUTABLE
    AS $$
    declare
      res jsonb;
    begin
      execute format('select to_jsonb(%L::'|| type_::text || ')', val)  into res;
      return res;
    end
    $$;


--
-- Name: check_equality_op(realtime.equality_op, regtype, text, text); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.check_equality_op(op realtime.equality_op, type_ regtype, val_1 text, val_2 text) RETURNS boolean
    LANGUAGE plpgsql IMMUTABLE
    AS $$
      /*
      Casts *val_1* and *val_2* as type *type_* and check the *op* condition for truthiness
      */
      declare
          op_symbol text = (
              case
                  when op = 'eq' then '='
                  when op = 'neq' then '!='
                  when op = 'lt' then '<'
                  when op = 'lte' then '<='
                  when op = 'gt' then '>'
                  when op = 'gte' then '>='
                  when op = 'in' then '= any'
                  else 'UNKNOWN OP'
              end
          );
          res boolean;
      begin
          execute format(
              'select %L::'|| type_::text || ' ' || op_symbol
              || ' ( %L::'
              || (
                  case
                      when op = 'in' then type_::text || '[]'
                      else type_::text end
              )
              || ')', val_1, val_2) into res;
          return res;
      end;
      $$;


--
-- Name: is_visible_through_filters(realtime.wal_column[], realtime.user_defined_filter[]); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.is_visible_through_filters(columns realtime.wal_column[], filters realtime.user_defined_filter[]) RETURNS boolean
    LANGUAGE sql IMMUTABLE
    AS $_$
    /*
    Should the record be visible (true) or filtered out (false) after *filters* are applied
    */
        select
            -- Default to allowed when no filters present
            $2 is null -- no filters. this should not happen because subscriptions has a default
            or array_length($2, 1) is null -- array length of an empty array is null
            or bool_and(
                coalesce(
                    realtime.check_equality_op(
                        op:=f.op,
                        type_:=coalesce(
                            col.type_oid::regtype, -- null when wal2json version <= 2.4
                            col.type_name::regtype
                        ),
                        -- cast jsonb to text
                        val_1:=col.value #>> '{}',
                        val_2:=f.value
                    ),
                    false -- if null, filter does not match
                )
            )
        from
            unnest(filters) f
            join unnest(columns) col
                on f.column_name = col.name;
    $_$;


--
-- Name: list_changes(name, name, integer, integer); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.list_changes(publication name, slot_name name, max_changes integer, max_record_bytes integer) RETURNS SETOF realtime.wal_rls
    LANGUAGE sql
    SET log_min_messages TO 'fatal'
    AS $$
      with pub as (
        select
          concat_ws(
            ',',
            case when bool_or(pubinsert) then 'insert' else null end,
            case when bool_or(pubupdate) then 'update' else null end,
            case when bool_or(pubdelete) then 'delete' else null end
          ) as w2j_actions,
          coalesce(
            string_agg(
              realtime.quote_wal2json(format('%I.%I', schemaname, tablename)::regclass),
              ','
            ) filter (where ppt.tablename is not null and ppt.tablename not like '% %'),
            ''
          ) w2j_add_tables
        from
          pg_publication pp
          left join pg_publication_tables ppt
            on pp.pubname = ppt.pubname
        where
          pp.pubname = publication
        group by
          pp.pubname
        limit 1
      ),
      w2j as (
        select
          x.*, pub.w2j_add_tables
        from
          pub,
          pg_logical_slot_get_changes(
            slot_name, null, max_changes,
            'include-pk', 'true',
            'include-transaction', 'false',
            'include-timestamp', 'true',
            'include-type-oids', 'true',
            'format-version', '2',
            'actions', pub.w2j_actions,
            'add-tables', pub.w2j_add_tables
          ) x
      )
      select
        xyz.wal,
        xyz.is_rls_enabled,
        xyz.subscription_ids,
        xyz.errors
      from
        w2j,
        realtime.apply_rls(
          wal := w2j.data::jsonb,
          max_record_bytes := max_record_bytes
        ) xyz(wal, is_rls_enabled, subscription_ids, errors)
      where
        w2j.w2j_add_tables <> ''
        and xyz.subscription_ids[1] is not null
    $$;


--
-- Name: quote_wal2json(regclass); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.quote_wal2json(entity regclass) RETURNS text
    LANGUAGE sql IMMUTABLE STRICT
    AS $$
      select
        (
          select string_agg('' || ch,'')
          from unnest(string_to_array(nsp.nspname::text, null)) with ordinality x(ch, idx)
          where
            not (x.idx = 1 and x.ch = '"')
            and not (
              x.idx = array_length(string_to_array(nsp.nspname::text, null), 1)
              and x.ch = '"'
            )
        )
        || '.'
        || (
          select string_agg('' || ch,'')
          from unnest(string_to_array(pc.relname::text, null)) with ordinality x(ch, idx)
          where
            not (x.idx = 1 and x.ch = '"')
            and not (
              x.idx = array_length(string_to_array(nsp.nspname::text, null), 1)
              and x.ch = '"'
            )
          )
      from
        pg_class pc
        join pg_namespace nsp
          on pc.relnamespace = nsp.oid
      where
        pc.oid = entity
    $$;


--
-- Name: send(jsonb, text, text, boolean); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean DEFAULT true) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  BEGIN
    -- Set the topic configuration
    EXECUTE format('SET LOCAL realtime.topic TO %L', topic);

    -- Attempt to insert the message
    INSERT INTO realtime.messages (payload, event, topic, private, extension)
    VALUES (payload, event, topic, private, 'broadcast');
  EXCEPTION
    WHEN OTHERS THEN
      -- Capture and notify the error
      PERFORM pg_notify(
          'realtime:system',
          jsonb_build_object(
              'error', SQLERRM,
              'function', 'realtime.send',
              'event', event,
              'topic', topic,
              'private', private
          )::text
      );
  END;
END;
$$;


--
-- Name: subscription_check_filters(); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.subscription_check_filters() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    /*
    Validates that the user defined filters for a subscription:
    - refer to valid columns that the claimed role may access
    - values are coercable to the correct column type
    */
    declare
        col_names text[] = coalesce(
                array_agg(c.column_name order by c.ordinal_position),
                '{}'::text[]
            )
            from
                information_schema.columns c
            where
                format('%I.%I', c.table_schema, c.table_name)::regclass = new.entity
                and pg_catalog.has_column_privilege(
                    (new.claims ->> 'role'),
                    format('%I.%I', c.table_schema, c.table_name)::regclass,
                    c.column_name,
                    'SELECT'
                );
        filter realtime.user_defined_filter;
        col_type regtype;

        in_val jsonb;
    begin
        for filter in select * from unnest(new.filters) loop
            -- Filtered column is valid
            if not filter.column_name = any(col_names) then
                raise exception 'invalid column for filter %', filter.column_name;
            end if;

            -- Type is sanitized and safe for string interpolation
            col_type = (
                select atttypid::regtype
                from pg_catalog.pg_attribute
                where attrelid = new.entity
                      and attname = filter.column_name
            );
            if col_type is null then
                raise exception 'failed to lookup type for column %', filter.column_name;
            end if;

            -- Set maximum number of entries for in filter
            if filter.op = 'in'::realtime.equality_op then
                in_val = realtime.cast(filter.value, (col_type::text || '[]')::regtype);
                if coalesce(jsonb_array_length(in_val), 0) > 100 then
                    raise exception 'too many values for `in` filter. Maximum 100';
                end if;
            else
                -- raises an exception if value is not coercable to type
                perform realtime.cast(filter.value, col_type);
            end if;

        end loop;

        -- Apply consistent order to filters so the unique constraint on
        -- (subscription_id, entity, filters) can't be tricked by a different filter order
        new.filters = coalesce(
            array_agg(f order by f.column_name, f.op, f.value),
            '{}'
        ) from unnest(new.filters) f;

        return new;
    end;
    $$;


--
-- Name: to_regrole(text); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.to_regrole(role_name text) RETURNS regrole
    LANGUAGE sql IMMUTABLE
    AS $$ select role_name::regrole $$;


--
-- Name: topic(); Type: FUNCTION; Schema: realtime; Owner: -
--

CREATE FUNCTION realtime.topic() RETURNS text
    LANGUAGE sql STABLE
    AS $$
select nullif(current_setting('realtime.topic', true), '')::text;
$$;


--
-- Name: can_insert_object(text, text, uuid, jsonb); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.can_insert_object(bucketid text, name text, owner uuid, metadata jsonb) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  INSERT INTO "storage"."objects" ("bucket_id", "name", "owner", "metadata") VALUES (bucketid, name, owner, metadata);
  -- hack to rollback the successful insert
  RAISE sqlstate 'PT200' using
  message = 'ROLLBACK',
  detail = 'rollback successful insert';
END
$$;


--
-- Name: extension(text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.extension(name text) RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
_parts text[];
_filename text;
BEGIN
	select string_to_array(name, '/') into _parts;
	select _parts[array_length(_parts,1)] into _filename;
	-- @todo return the last part instead of 2
	return reverse(split_part(reverse(_filename), '.', 1));
END
$$;


--
-- Name: filename(text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.filename(name text) RETURNS text
    LANGUAGE plpgsql
    AS $$
DECLARE
_parts text[];
BEGIN
	select string_to_array(name, '/') into _parts;
	return _parts[array_length(_parts,1)];
END
$$;


--
-- Name: foldername(text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.foldername(name text) RETURNS text[]
    LANGUAGE plpgsql
    AS $$
DECLARE
_parts text[];
BEGIN
	select string_to_array(name, '/') into _parts;
	return _parts[1:array_length(_parts,1)-1];
END
$$;


--
-- Name: get_size_by_bucket(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.get_size_by_bucket() RETURNS TABLE(size bigint, bucket_id text)
    LANGUAGE plpgsql
    AS $$
BEGIN
    return query
        select sum((metadata->>'size')::int) as size, obj.bucket_id
        from "storage".objects as obj
        group by obj.bucket_id;
END
$$;


--
-- Name: list_multipart_uploads_with_delimiter(text, text, text, integer, text, text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.list_multipart_uploads_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer DEFAULT 100, next_key_token text DEFAULT ''::text, next_upload_token text DEFAULT ''::text) RETURNS TABLE(key text, id text, created_at timestamp with time zone)
    LANGUAGE plpgsql
    AS $_$
BEGIN
    RETURN QUERY EXECUTE
        'SELECT DISTINCT ON(key COLLATE "C") * from (
            SELECT
                CASE
                    WHEN position($2 IN substring(key from length($1) + 1)) > 0 THEN
                        substring(key from 1 for length($1) + position($2 IN substring(key from length($1) + 1)))
                    ELSE
                        key
                END AS key, id, created_at
            FROM
                storage.s3_multipart_uploads
            WHERE
                bucket_id = $5 AND
                key ILIKE $1 || ''%'' AND
                CASE
                    WHEN $4 != '''' AND $6 = '''' THEN
                        CASE
                            WHEN position($2 IN substring(key from length($1) + 1)) > 0 THEN
                                substring(key from 1 for length($1) + position($2 IN substring(key from length($1) + 1))) COLLATE "C" > $4
                            ELSE
                                key COLLATE "C" > $4
                            END
                    ELSE
                        true
                END AND
                CASE
                    WHEN $6 != '''' THEN
                        id COLLATE "C" > $6
                    ELSE
                        true
                    END
            ORDER BY
                key COLLATE "C" ASC, created_at ASC) as e order by key COLLATE "C" LIMIT $3'
        USING prefix_param, delimiter_param, max_keys, next_key_token, bucket_id, next_upload_token;
END;
$_$;


--
-- Name: list_objects_with_delimiter(text, text, text, integer, text, text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.list_objects_with_delimiter(bucket_id text, prefix_param text, delimiter_param text, max_keys integer DEFAULT 100, start_after text DEFAULT ''::text, next_token text DEFAULT ''::text) RETURNS TABLE(name text, id uuid, metadata jsonb, updated_at timestamp with time zone)
    LANGUAGE plpgsql
    AS $_$
BEGIN
    RETURN QUERY EXECUTE
        'SELECT DISTINCT ON(name COLLATE "C") * from (
            SELECT
                CASE
                    WHEN position($2 IN substring(name from length($1) + 1)) > 0 THEN
                        substring(name from 1 for length($1) + position($2 IN substring(name from length($1) + 1)))
                    ELSE
                        name
                END AS name, id, metadata, updated_at
            FROM
                storage.objects
            WHERE
                bucket_id = $5 AND
                name ILIKE $1 || ''%'' AND
                CASE
                    WHEN $6 != '''' THEN
                    name COLLATE "C" > $6
                ELSE true END
                AND CASE
                    WHEN $4 != '''' THEN
                        CASE
                            WHEN position($2 IN substring(name from length($1) + 1)) > 0 THEN
                                substring(name from 1 for length($1) + position($2 IN substring(name from length($1) + 1))) COLLATE "C" > $4
                            ELSE
                                name COLLATE "C" > $4
                            END
                    ELSE
                        true
                END
            ORDER BY
                name COLLATE "C" ASC) as e order by name COLLATE "C" LIMIT $3'
        USING prefix_param, delimiter_param, max_keys, next_token, bucket_id, start_after;
END;
$_$;


--
-- Name: operation(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.operation() RETURNS text
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
    RETURN current_setting('storage.operation', true);
END;
$$;


--
-- Name: search(text, text, integer, integer, integer, text, text, text); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.search(prefix text, bucketname text, limits integer DEFAULT 100, levels integer DEFAULT 1, offsets integer DEFAULT 0, search text DEFAULT ''::text, sortcolumn text DEFAULT 'name'::text, sortorder text DEFAULT 'asc'::text) RETURNS TABLE(name text, id uuid, updated_at timestamp with time zone, created_at timestamp with time zone, last_accessed_at timestamp with time zone, metadata jsonb)
    LANGUAGE plpgsql STABLE
    AS $_$
declare
  v_order_by text;
  v_sort_order text;
begin
  case
    when sortcolumn = 'name' then
      v_order_by = 'name';
    when sortcolumn = 'updated_at' then
      v_order_by = 'updated_at';
    when sortcolumn = 'created_at' then
      v_order_by = 'created_at';
    when sortcolumn = 'last_accessed_at' then
      v_order_by = 'last_accessed_at';
    else
      v_order_by = 'name';
  end case;

  case
    when sortorder = 'asc' then
      v_sort_order = 'asc';
    when sortorder = 'desc' then
      v_sort_order = 'desc';
    else
      v_sort_order = 'asc';
  end case;

  v_order_by = v_order_by || ' ' || v_sort_order;

  return query execute
    'with folders as (
       select path_tokens[$1] as folder
       from storage.objects
         where objects.name ilike $2 || $3 || ''%''
           and bucket_id = $4
           and array_length(objects.path_tokens, 1) <> $1
       group by folder
       order by folder ' || v_sort_order || '
     )
     (select folder as "name",
            null as id,
            null as updated_at,
            null as created_at,
            null as last_accessed_at,
            null as metadata from folders)
     union all
     (select path_tokens[$1] as "name",
            id,
            updated_at,
            created_at,
            last_accessed_at,
            metadata
     from storage.objects
     where objects.name ilike $2 || $3 || ''%''
       and bucket_id = $4
       and array_length(objects.path_tokens, 1) = $1
     order by ' || v_order_by || ')
     limit $5
     offset $6' using levels, prefix, search, bucketname, limits, offsets;
end;
$_$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: storage; Owner: -
--

CREATE FUNCTION storage.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW; 
END;
$$;


--
-- Name: secrets_encrypt_secret_secret(); Type: FUNCTION; Schema: vault; Owner: -
--

CREATE FUNCTION vault.secrets_encrypt_secret_secret() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
		BEGIN
		        new.secret = CASE WHEN new.secret IS NULL THEN NULL ELSE
			CASE WHEN new.key_id IS NULL THEN NULL ELSE pg_catalog.encode(
			  pgsodium.crypto_aead_det_encrypt(
				pg_catalog.convert_to(new.secret, 'utf8'),
				pg_catalog.convert_to((new.id::text || new.description::text || new.created_at::text || new.updated_at::text)::text, 'utf8'),
				new.key_id::uuid,
				new.nonce
			  ),
				'base64') END END;
		RETURN new;
		END;
		$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: audit_log_entries; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.audit_log_entries (
    instance_id uuid,
    id uuid NOT NULL,
    payload json,
    created_at timestamp with time zone,
    ip_address character varying(64) DEFAULT ''::character varying NOT NULL
);


--
-- Name: TABLE audit_log_entries; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.audit_log_entries IS 'Auth: Audit trail for user actions.';


--
-- Name: flow_state; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.flow_state (
    id uuid NOT NULL,
    user_id uuid,
    auth_code text NOT NULL,
    code_challenge_method auth.code_challenge_method NOT NULL,
    code_challenge text NOT NULL,
    provider_type text NOT NULL,
    provider_access_token text,
    provider_refresh_token text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    authentication_method text NOT NULL,
    auth_code_issued_at timestamp with time zone
);


--
-- Name: TABLE flow_state; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.flow_state IS 'stores metadata for pkce logins';


--
-- Name: identities; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.identities (
    provider_id text NOT NULL,
    user_id uuid NOT NULL,
    identity_data jsonb NOT NULL,
    provider text NOT NULL,
    last_sign_in_at timestamp with time zone,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    email text GENERATED ALWAYS AS (lower((identity_data ->> 'email'::text))) STORED,
    id uuid DEFAULT gen_random_uuid() NOT NULL
);


--
-- Name: TABLE identities; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.identities IS 'Auth: Stores identities associated to a user.';


--
-- Name: COLUMN identities.email; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON COLUMN auth.identities.email IS 'Auth: Email is a generated column that references the optional email property in the identity_data';


--
-- Name: instances; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.instances (
    id uuid NOT NULL,
    uuid uuid,
    raw_base_config text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


--
-- Name: TABLE instances; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.instances IS 'Auth: Manages users across multiple sites.';


--
-- Name: mfa_amr_claims; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.mfa_amr_claims (
    session_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    authentication_method text NOT NULL,
    id uuid NOT NULL
);


--
-- Name: TABLE mfa_amr_claims; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.mfa_amr_claims IS 'auth: stores authenticator method reference claims for multi factor authentication';


--
-- Name: mfa_challenges; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.mfa_challenges (
    id uuid NOT NULL,
    factor_id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    verified_at timestamp with time zone,
    ip_address inet NOT NULL,
    otp_code text,
    web_authn_session_data jsonb
);


--
-- Name: TABLE mfa_challenges; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.mfa_challenges IS 'auth: stores metadata about challenge requests made';


--
-- Name: mfa_factors; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.mfa_factors (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    friendly_name text,
    factor_type auth.factor_type NOT NULL,
    status auth.factor_status NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    secret text,
    phone text,
    last_challenged_at timestamp with time zone,
    web_authn_credential jsonb,
    web_authn_aaguid uuid
);


--
-- Name: TABLE mfa_factors; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.mfa_factors IS 'auth: stores metadata about factors';


--
-- Name: one_time_tokens; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.one_time_tokens (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    token_type auth.one_time_token_type NOT NULL,
    token_hash text NOT NULL,
    relates_to text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT one_time_tokens_token_hash_check CHECK ((char_length(token_hash) > 0))
);


--
-- Name: refresh_tokens; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.refresh_tokens (
    instance_id uuid,
    id bigint NOT NULL,
    token character varying(255),
    user_id character varying(255),
    revoked boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    parent character varying(255),
    session_id uuid
);


--
-- Name: TABLE refresh_tokens; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.refresh_tokens IS 'Auth: Store of tokens used to refresh JWT tokens once they expire.';


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE; Schema: auth; Owner: -
--

CREATE SEQUENCE auth.refresh_tokens_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: auth; Owner: -
--

ALTER SEQUENCE auth.refresh_tokens_id_seq OWNED BY auth.refresh_tokens.id;


--
-- Name: saml_providers; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.saml_providers (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    entity_id text NOT NULL,
    metadata_xml text NOT NULL,
    metadata_url text,
    attribute_mapping jsonb,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    name_id_format text,
    CONSTRAINT "entity_id not empty" CHECK ((char_length(entity_id) > 0)),
    CONSTRAINT "metadata_url not empty" CHECK (((metadata_url = NULL::text) OR (char_length(metadata_url) > 0))),
    CONSTRAINT "metadata_xml not empty" CHECK ((char_length(metadata_xml) > 0))
);


--
-- Name: TABLE saml_providers; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.saml_providers IS 'Auth: Manages SAML Identity Provider connections.';


--
-- Name: saml_relay_states; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.saml_relay_states (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    request_id text NOT NULL,
    for_email text,
    redirect_to text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    flow_state_id uuid,
    CONSTRAINT "request_id not empty" CHECK ((char_length(request_id) > 0))
);


--
-- Name: TABLE saml_relay_states; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.saml_relay_states IS 'Auth: Contains SAML Relay State information for each Service Provider initiated login.';


--
-- Name: schema_migrations; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.schema_migrations (
    version character varying(255) NOT NULL
);


--
-- Name: TABLE schema_migrations; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.schema_migrations IS 'Auth: Manages updates to the auth system.';


--
-- Name: sessions; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.sessions (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    factor_id uuid,
    aal auth.aal_level,
    not_after timestamp with time zone,
    refreshed_at timestamp without time zone,
    user_agent text,
    ip inet,
    tag text
);


--
-- Name: TABLE sessions; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.sessions IS 'Auth: Stores session data associated to a user.';


--
-- Name: COLUMN sessions.not_after; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON COLUMN auth.sessions.not_after IS 'Auth: Not after is a nullable column that contains a timestamp after which the session should be regarded as expired.';


--
-- Name: sso_domains; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.sso_domains (
    id uuid NOT NULL,
    sso_provider_id uuid NOT NULL,
    domain text NOT NULL,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    CONSTRAINT "domain not empty" CHECK ((char_length(domain) > 0))
);


--
-- Name: TABLE sso_domains; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.sso_domains IS 'Auth: Manages SSO email address domain mapping to an SSO Identity Provider.';


--
-- Name: sso_providers; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.sso_providers (
    id uuid NOT NULL,
    resource_id text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    CONSTRAINT "resource_id not empty" CHECK (((resource_id = NULL::text) OR (char_length(resource_id) > 0)))
);


--
-- Name: TABLE sso_providers; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.sso_providers IS 'Auth: Manages SSO identity provider information; see saml_providers for SAML.';


--
-- Name: COLUMN sso_providers.resource_id; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON COLUMN auth.sso_providers.resource_id IS 'Auth: Uniquely identifies a SSO provider according to a user-chosen resource ID (case insensitive), useful in infrastructure as code.';


--
-- Name: users; Type: TABLE; Schema: auth; Owner: -
--

CREATE TABLE auth.users (
    instance_id uuid,
    id uuid NOT NULL,
    aud character varying(255),
    role character varying(255),
    email character varying(255),
    encrypted_password character varying(255),
    email_confirmed_at timestamp with time zone,
    invited_at timestamp with time zone,
    confirmation_token character varying(255),
    confirmation_sent_at timestamp with time zone,
    recovery_token character varying(255),
    recovery_sent_at timestamp with time zone,
    email_change_token_new character varying(255),
    email_change character varying(255),
    email_change_sent_at timestamp with time zone,
    last_sign_in_at timestamp with time zone,
    raw_app_meta_data jsonb,
    raw_user_meta_data jsonb,
    is_super_admin boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    phone text DEFAULT NULL::character varying,
    phone_confirmed_at timestamp with time zone,
    phone_change text DEFAULT ''::character varying,
    phone_change_token character varying(255) DEFAULT ''::character varying,
    phone_change_sent_at timestamp with time zone,
    confirmed_at timestamp with time zone GENERATED ALWAYS AS (LEAST(email_confirmed_at, phone_confirmed_at)) STORED,
    email_change_token_current character varying(255) DEFAULT ''::character varying,
    email_change_confirm_status smallint DEFAULT 0,
    banned_until timestamp with time zone,
    reauthentication_token character varying(255) DEFAULT ''::character varying,
    reauthentication_sent_at timestamp with time zone,
    is_sso_user boolean DEFAULT false NOT NULL,
    deleted_at timestamp with time zone,
    is_anonymous boolean DEFAULT false NOT NULL,
    CONSTRAINT users_email_change_confirm_status_check CHECK (((email_change_confirm_status >= 0) AND (email_change_confirm_status <= 2)))
);


--
-- Name: TABLE users; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON TABLE auth.users IS 'Auth: Stores user login data within a secure schema.';


--
-- Name: COLUMN users.is_sso_user; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON COLUMN auth.users.is_sso_user IS 'Auth: Set this column to true when the account comes from SSO. These accounts can have duplicate emails.';


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: chat_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_members (
    id integer NOT NULL,
    room_id integer,
    auth0_user_id character varying,
    joined_at timestamp without time zone,
    user_id integer
);


--
-- Name: chat_members_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chat_members_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chat_members_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chat_members_id_seq OWNED BY public.chat_members.id;


--
-- Name: chat_rooms; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_rooms (
    id integer NOT NULL,
    stream_channel_id character varying,
    stream_channel_type character varying,
    name character varying,
    created_at timestamp without time zone,
    event_id integer,
    is_direct boolean
);


--
-- Name: chat_rooms_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.chat_rooms_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: chat_rooms_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.chat_rooms_id_seq OWNED BY public.chat_rooms.id;


--
-- Name: class; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.class (
    id integer NOT NULL,
    name character varying NOT NULL,
    description text,
    duration integer NOT NULL,
    max_capacity integer NOT NULL,
    difficulty_level public."classdifficultyLevel" NOT NULL,
    category_id integer,
    category_enum public.classcategory,
    is_active boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    created_by integer,
    gym_id integer NOT NULL
);


--
-- Name: class_category_custom; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.class_category_custom (
    id integer NOT NULL,
    name character varying NOT NULL,
    description text,
    color character varying,
    icon character varying,
    is_active boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    created_by integer,
    gym_id integer NOT NULL
);


--
-- Name: class_category_custom_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.class_category_custom_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: class_category_custom_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.class_category_custom_id_seq OWNED BY public.class_category_custom.id;


--
-- Name: class_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.class_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: class_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.class_id_seq OWNED BY public.class.id;


--
-- Name: class_participation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.class_participation (
    id integer NOT NULL,
    session_id integer NOT NULL,
    member_id integer NOT NULL,
    status public.classparticipationstatus,
    registration_time timestamp with time zone DEFAULT now(),
    attendance_time timestamp with time zone,
    cancellation_time timestamp with time zone,
    cancellation_reason character varying,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    gym_id integer NOT NULL
);


--
-- Name: class_participation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.class_participation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: class_participation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.class_participation_id_seq OWNED BY public.class_participation.id;


--
-- Name: class_session; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.class_session (
    id integer NOT NULL,
    class_id integer NOT NULL,
    trainer_id integer NOT NULL,
    start_time timestamp without time zone NOT NULL,
    end_time timestamp without time zone NOT NULL,
    room character varying,
    is_recurring boolean,
    recurrence_pattern character varying,
    status public.classsessionstatus,
    current_participants integer,
    notes text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    created_by integer,
    gym_id integer NOT NULL
);


--
-- Name: class_session_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.class_session_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: class_session_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.class_session_id_seq OWNED BY public.class_session.id;


--
-- Name: device_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_tokens (
    id uuid DEFAULT extensions.uuid_generate_v4() NOT NULL,
    user_id character varying NOT NULL,
    device_token character varying(255) NOT NULL,
    platform character varying(20) NOT NULL,
    is_active boolean DEFAULT true,
    last_used timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


--
-- Name: event_participations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.event_participations (
    id integer NOT NULL,
    event_id integer NOT NULL,
    member_id integer NOT NULL,
    status public.eventparticipationstatus,
    attended boolean,
    registered_at timestamp without time zone,
    updated_at timestamp without time zone,
    gym_id integer NOT NULL
);


--
-- Name: event_participations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.event_participations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: event_participations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.event_participations_id_seq OWNED BY public.event_participations.id;


--
-- Name: events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.events (
    id integer NOT NULL,
    title character varying(100) NOT NULL,
    description text,
    start_time timestamp without time zone NOT NULL,
    end_time timestamp without time zone NOT NULL,
    location character varying(100),
    max_participants integer NOT NULL,
    status public.eventstatus,
    creator_id integer NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    gym_id integer NOT NULL
);


--
-- Name: events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.events_id_seq OWNED BY public.events.id;


--
-- Name: gym_hours; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.gym_hours (
    id integer NOT NULL,
    day_of_week integer NOT NULL,
    open_time time without time zone,
    close_time time without time zone,
    is_closed boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    gym_id integer NOT NULL,
    CONSTRAINT check_valid_day_of_week CHECK (((day_of_week >= 0) AND (day_of_week <= 6)))
);


--
-- Name: gym_hours_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.gym_hours_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gym_hours_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.gym_hours_id_seq OWNED BY public.gym_hours.id;


--
-- Name: gym_special_hours; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.gym_special_hours (
    id integer NOT NULL,
    date date NOT NULL,
    open_time time without time zone,
    close_time time without time zone,
    is_closed boolean,
    description character varying,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    created_by integer,
    gym_id integer NOT NULL
);


--
-- Name: gym_special_hours_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.gym_special_hours_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gym_special_hours_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.gym_special_hours_id_seq OWNED BY public.gym_special_hours.id;


--
-- Name: gyms; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.gyms (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    subdomain character varying(100) NOT NULL,
    logo_url character varying(255),
    address character varying(255),
    phone character varying(20),
    email character varying(100),
    description character varying(500),
    is_active boolean,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: gyms_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.gyms_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gyms_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.gyms_id_seq OWNED BY public.gyms.id;


--
-- Name: trainermemberrelationship; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trainermemberrelationship (
    id integer NOT NULL,
    trainer_id integer NOT NULL,
    member_id integer NOT NULL,
    status public.relationshipstatus,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    start_date timestamp with time zone,
    end_date timestamp with time zone,
    notes character varying,
    created_by integer
);


--
-- Name: trainermemberrelationship_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.trainermemberrelationship_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: trainermemberrelationship_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.trainermemberrelationship_id_seq OWNED BY public.trainermemberrelationship.id;


--
-- Name: user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."user" (
    id integer NOT NULL,
    email character varying NOT NULL,
    is_active boolean,
    is_superuser boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    auth0_id character varying,
    picture character varying,
    locale character varying(5),
    auth0_metadata text,
    role public.userrole DEFAULT 'MEMBER'::public.userrole,
    phone_number character varying(20),
    birth_date timestamp without time zone,
    height double precision,
    weight double precision,
    bio text,
    goals text,
    health_conditions text,
    first_name character varying,
    last_name character varying
);


--
-- Name: user_gyms; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_gyms (
    id integer NOT NULL,
    user_id integer NOT NULL,
    gym_id integer NOT NULL,
    role public.gymroletype NOT NULL,
    created_at timestamp without time zone
);


--
-- Name: user_gyms_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_gyms_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_gyms_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_gyms_id_seq OWNED BY public.user_gyms.id;


--
-- Name: user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_id_seq OWNED BY public."user".id;


--
-- Name: messages; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.messages (
    topic text NOT NULL,
    extension text NOT NULL,
    payload jsonb,
    event text,
    private boolean DEFAULT false,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    inserted_at timestamp without time zone DEFAULT now() NOT NULL,
    id uuid DEFAULT gen_random_uuid() NOT NULL
)
PARTITION BY RANGE (inserted_at);


--
-- Name: schema_migrations; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.schema_migrations (
    version bigint NOT NULL,
    inserted_at timestamp(0) without time zone
);


--
-- Name: subscription; Type: TABLE; Schema: realtime; Owner: -
--

CREATE TABLE realtime.subscription (
    id bigint NOT NULL,
    subscription_id uuid NOT NULL,
    entity regclass NOT NULL,
    filters realtime.user_defined_filter[] DEFAULT '{}'::realtime.user_defined_filter[] NOT NULL,
    claims jsonb NOT NULL,
    claims_role regrole GENERATED ALWAYS AS (realtime.to_regrole((claims ->> 'role'::text))) STORED NOT NULL,
    created_at timestamp without time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);


--
-- Name: subscription_id_seq; Type: SEQUENCE; Schema: realtime; Owner: -
--

ALTER TABLE realtime.subscription ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME realtime.subscription_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: buckets; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.buckets (
    id text NOT NULL,
    name text NOT NULL,
    owner uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    public boolean DEFAULT false,
    avif_autodetection boolean DEFAULT false,
    file_size_limit bigint,
    allowed_mime_types text[],
    owner_id text
);


--
-- Name: COLUMN buckets.owner; Type: COMMENT; Schema: storage; Owner: -
--

COMMENT ON COLUMN storage.buckets.owner IS 'Field is deprecated, use owner_id instead';


--
-- Name: migrations; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.migrations (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    hash character varying(40) NOT NULL,
    executed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: objects; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.objects (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    bucket_id text,
    name text,
    owner uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    last_accessed_at timestamp with time zone DEFAULT now(),
    metadata jsonb,
    path_tokens text[] GENERATED ALWAYS AS (string_to_array(name, '/'::text)) STORED,
    version text,
    owner_id text,
    user_metadata jsonb
);


--
-- Name: COLUMN objects.owner; Type: COMMENT; Schema: storage; Owner: -
--

COMMENT ON COLUMN storage.objects.owner IS 'Field is deprecated, use owner_id instead';


--
-- Name: s3_multipart_uploads; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.s3_multipart_uploads (
    id text NOT NULL,
    in_progress_size bigint DEFAULT 0 NOT NULL,
    upload_signature text NOT NULL,
    bucket_id text NOT NULL,
    key text NOT NULL COLLATE pg_catalog."C",
    version text NOT NULL,
    owner_id text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    user_metadata jsonb
);


--
-- Name: s3_multipart_uploads_parts; Type: TABLE; Schema: storage; Owner: -
--

CREATE TABLE storage.s3_multipart_uploads_parts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    upload_id text NOT NULL,
    size bigint DEFAULT 0 NOT NULL,
    part_number integer NOT NULL,
    bucket_id text NOT NULL,
    key text NOT NULL COLLATE pg_catalog."C",
    etag text NOT NULL,
    owner_id text,
    version text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: decrypted_secrets; Type: VIEW; Schema: vault; Owner: -
--

CREATE VIEW vault.decrypted_secrets AS
 SELECT secrets.id,
    secrets.name,
    secrets.description,
    secrets.secret,
        CASE
            WHEN (secrets.secret IS NULL) THEN NULL::text
            ELSE
            CASE
                WHEN (secrets.key_id IS NULL) THEN NULL::text
                ELSE convert_from(pgsodium.crypto_aead_det_decrypt(decode(secrets.secret, 'base64'::text), convert_to(((((secrets.id)::text || secrets.description) || (secrets.created_at)::text) || (secrets.updated_at)::text), 'utf8'::name), secrets.key_id, secrets.nonce), 'utf8'::name)
            END
        END AS decrypted_secret,
    secrets.key_id,
    secrets.nonce,
    secrets.created_at,
    secrets.updated_at
   FROM vault.secrets;


--
-- Name: refresh_tokens id; Type: DEFAULT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.refresh_tokens ALTER COLUMN id SET DEFAULT nextval('auth.refresh_tokens_id_seq'::regclass);


--
-- Name: chat_members id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_members ALTER COLUMN id SET DEFAULT nextval('public.chat_members_id_seq'::regclass);


--
-- Name: chat_rooms id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_rooms ALTER COLUMN id SET DEFAULT nextval('public.chat_rooms_id_seq'::regclass);


--
-- Name: class id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class ALTER COLUMN id SET DEFAULT nextval('public.class_id_seq'::regclass);


--
-- Name: class_category_custom id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_category_custom ALTER COLUMN id SET DEFAULT nextval('public.class_category_custom_id_seq'::regclass);


--
-- Name: class_participation id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_participation ALTER COLUMN id SET DEFAULT nextval('public.class_participation_id_seq'::regclass);


--
-- Name: class_session id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_session ALTER COLUMN id SET DEFAULT nextval('public.class_session_id_seq'::regclass);


--
-- Name: event_participations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_participations ALTER COLUMN id SET DEFAULT nextval('public.event_participations_id_seq'::regclass);


--
-- Name: events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events ALTER COLUMN id SET DEFAULT nextval('public.events_id_seq'::regclass);


--
-- Name: gym_hours id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gym_hours ALTER COLUMN id SET DEFAULT nextval('public.gym_hours_id_seq'::regclass);


--
-- Name: gym_special_hours id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gym_special_hours ALTER COLUMN id SET DEFAULT nextval('public.gym_special_hours_id_seq'::regclass);


--
-- Name: gyms id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gyms ALTER COLUMN id SET DEFAULT nextval('public.gyms_id_seq'::regclass);


--
-- Name: trainermemberrelationship id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trainermemberrelationship ALTER COLUMN id SET DEFAULT nextval('public.trainermemberrelationship_id_seq'::regclass);


--
-- Name: user id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user" ALTER COLUMN id SET DEFAULT nextval('public.user_id_seq'::regclass);


--
-- Name: user_gyms id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_gyms ALTER COLUMN id SET DEFAULT nextval('public.user_gyms_id_seq'::regclass);


--
-- Data for Name: audit_log_entries; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.audit_log_entries (instance_id, id, payload, created_at, ip_address) FROM stdin;
\.


--
-- Data for Name: flow_state; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.flow_state (id, user_id, auth_code, code_challenge_method, code_challenge, provider_type, provider_access_token, provider_refresh_token, created_at, updated_at, authentication_method, auth_code_issued_at) FROM stdin;
\.


--
-- Data for Name: identities; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.identities (provider_id, user_id, identity_data, provider, last_sign_in_at, created_at, updated_at, id) FROM stdin;
\.


--
-- Data for Name: instances; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.instances (id, uuid, raw_base_config, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: mfa_amr_claims; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.mfa_amr_claims (session_id, created_at, updated_at, authentication_method, id) FROM stdin;
\.


--
-- Data for Name: mfa_challenges; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.mfa_challenges (id, factor_id, created_at, verified_at, ip_address, otp_code, web_authn_session_data) FROM stdin;
\.


--
-- Data for Name: mfa_factors; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.mfa_factors (id, user_id, friendly_name, factor_type, status, created_at, updated_at, secret, phone, last_challenged_at, web_authn_credential, web_authn_aaguid) FROM stdin;
\.


--
-- Data for Name: one_time_tokens; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.one_time_tokens (id, user_id, token_type, token_hash, relates_to, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: refresh_tokens; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.refresh_tokens (instance_id, id, token, user_id, revoked, created_at, updated_at, parent, session_id) FROM stdin;
\.


--
-- Data for Name: saml_providers; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.saml_providers (id, sso_provider_id, entity_id, metadata_xml, metadata_url, attribute_mapping, created_at, updated_at, name_id_format) FROM stdin;
\.


--
-- Data for Name: saml_relay_states; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.saml_relay_states (id, sso_provider_id, request_id, for_email, redirect_to, created_at, updated_at, flow_state_id) FROM stdin;
\.


--
-- Data for Name: schema_migrations; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.schema_migrations (version) FROM stdin;
20171026211738
20171026211808
20171026211834
20180103212743
20180108183307
20180119214651
20180125194653
00
20210710035447
20210722035447
20210730183235
20210909172000
20210927181326
20211122151130
20211124214934
20211202183645
20220114185221
20220114185340
20220224000811
20220323170000
20220429102000
20220531120530
20220614074223
20220811173540
20221003041349
20221003041400
20221011041400
20221020193600
20221021073300
20221021082433
20221027105023
20221114143122
20221114143410
20221125140132
20221208132122
20221215195500
20221215195800
20221215195900
20230116124310
20230116124412
20230131181311
20230322519590
20230402418590
20230411005111
20230508135423
20230523124323
20230818113222
20230914180801
20231027141322
20231114161723
20231117164230
20240115144230
20240214120130
20240306115329
20240314092811
20240427152123
20240612123726
20240729123726
20240802193726
20240806073726
20241009103726
\.


--
-- Data for Name: sessions; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.sessions (id, user_id, created_at, updated_at, factor_id, aal, not_after, refreshed_at, user_agent, ip, tag) FROM stdin;
\.


--
-- Data for Name: sso_domains; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.sso_domains (id, sso_provider_id, domain, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: sso_providers; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.sso_providers (id, resource_id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: auth; Owner: -
--

COPY auth.users (instance_id, id, aud, role, email, encrypted_password, email_confirmed_at, invited_at, confirmation_token, confirmation_sent_at, recovery_token, recovery_sent_at, email_change_token_new, email_change, email_change_sent_at, last_sign_in_at, raw_app_meta_data, raw_user_meta_data, is_super_admin, created_at, updated_at, phone, phone_confirmed_at, phone_change, phone_change_token, phone_change_sent_at, email_change_token_current, email_change_confirm_status, banned_until, reauthentication_token, reauthentication_sent_at, is_sso_user, deleted_at, is_anonymous) FROM stdin;
\.


--
-- Data for Name: key; Type: TABLE DATA; Schema: pgsodium; Owner: -
--

COPY pgsodium.key (id, status, created, expires, key_type, key_id, key_context, name, associated_data, raw_key, raw_key_nonce, parent_key, comment, user_data) FROM stdin;
\.


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
402f9b8ef40e
\.


--
-- Data for Name: chat_members; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.chat_members (id, room_id, auth0_user_id, joined_at, user_id) FROM stdin;
1	2	auth0-67d5d64d64ccf1c522a6950b	2025-03-17 07:04:16.874188	\N
2	2	alexmontesino96	2025-03-17 07:04:16.87419	\N
6	5	auth0_67d5d64d64ccf1c522a6950b	2025-04-01 20:26:38.526446	\N
39	37	7	2025-04-06 15:00:01.262602	\N
40	38	7	2025-04-06 15:00:11.745831	\N
43	40	7	2025-04-06 15:09:40.218927	\N
55	46	4	2025-04-11 02:49:01.72285	\N
3	2	auth0|67d5d64d64ccf1c522a6950b	2025-03-17 07:04:16.874192	4
4	3	auth0|67d5d64d64ccf1c522a6950b	2025-03-17 07:24:29.18181	4
5	3	auth0|67d615b1a9ea8e1393906d4d	2025-03-17 07:24:29.181813	2
7	6	auth0|67d5d64d64ccf1c522a6950b	2025-04-01 20:27:48.457588	4
8	7	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:22:10.868306	4
9	8	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:23:15.118548	4
10	9	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:25:09.956133	4
11	10	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:25:26.23047	4
12	11	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:26:26.60434	4
13	12	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:30:36.090472	4
14	13	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:30:38.307945	4
15	14	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:30:40.082986	4
16	15	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:43:39.125364	4
17	16	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:43:41.683302	4
18	17	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:43:43.708724	4
19	18	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:43:49.248775	4
20	19	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:45:27.424404	4
21	20	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:45:30.076523	4
22	21	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:45:32.054581	4
23	22	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:45:37.668204	4
24	23	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:50:03.341107	4
25	24	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:50:05.826626	4
26	25	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:50:07.617143	4
27	26	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:50:13.086527	4
28	27	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:50:38.478059	4
29	28	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:50:40.780613	4
30	29	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:50:42.529292	4
31	30	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:50:48.386421	4
32	31	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:51:45.999858	4
33	32	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:51:48.325793	4
34	33	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:51:50.063214	4
35	34	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 02:51:56.421788	4
36	35	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 03:16:27.939352	4
37	36	auth0|67d5d64d64ccf1c522a6950b	2025-04-04 03:16:35.373923	4
38	37	auth0|67ef66dfcb9e2a66485f2dde	2025-04-06 15:00:01.2626	6
41	38	auth0|67ef66dfcb9e2a66485f2dde	2025-04-06 15:00:11.745833	6
44	40	auth0|67ef66dfcb9e2a66485f2dde	2025-04-06 15:09:40.21893	6
46	41	auth0|67d5d64d64ccf1c522a6950b	2025-04-09 04:33:26.365446	4
47	42	auth0|67d5d64d64ccf1c522a6950b	2025-04-09 04:34:33.407862	4
48	43	auth0|67d5d64d64ccf1c522a6950b	2025-04-09 04:34:57.837762	4
49	44	auth0|67d5d64d64ccf1c522a6950b	2025-04-09 04:36:31.426159	4
50	45	auth0|67d5d64d64ccf1c522a6950b	2025-04-09 04:39:09.206793	4
51	46	auth0|67d5d64d64ccf1c522a6950b	2025-04-09 05:08:51.963033	4
52	47	auth0|67ef66dfcb9e2a66485f2dde	2025-04-09 05:19:07.798118	6
53	48	auth0|67d5d64d64ccf1c522a6950b	2025-04-09 07:20:59.878922	4
54	49	auth0|67d5d64d64ccf1c522a6950b	2025-04-11 02:40:50.625492	4
56	50	\N	2025-04-11 03:38:19.094967	4
57	51	\N	2025-04-11 04:05:13.812843	4
58	52	\N	2025-04-11 04:15:20.151087	4
59	53	\N	2025-04-11 05:10:17.130933	4
\.


--
-- Data for Name: chat_rooms; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.chat_rooms (id, stream_channel_id, stream_channel_type, name, created_at, event_id, is_direct) FROM stdin;
2	room-prueba-auth0-67d5d64d64ccf1c522a6950b	messaging	prueba	2025-03-17 07:04:16.360183	1	f
3	dm-auth0-67d5d64d64ccf1c522a6950b-auth0-67d615b1a9ea8e1393906d4d	messaging	Chat auth0-67d5d64d64ccf1c522a6950b-auth0-67d615b1a9ea8e1393906d4d	2025-03-17 07:24:28.733764	\N	t
5	event_6_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Recogida de basura playa	2025-04-01 20:26:38.015078	6	f
6	event_7_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Recogida de basura playa	2025-04-01 20:27:47.987807	7	f
7	event_8_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento de Prueba 1743733329	2025-04-04 02:22:10.441192	8	f
8	event_9_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento de Prueba 1743733393	2025-04-04 02:23:14.647039	9	f
9	event_10_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento de Prueba 1743733507	2025-04-04 02:25:09.5389	10	f
10	event_11_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento de Prueba 1743733524	2025-04-04 02:25:25.746183	11	f
11	event_12_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento de Prueba 1743733583	2025-04-04 02:26:26.136174	12	f
14	event_15_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento para Próxima Semana 1743733838	2025-04-04 02:30:39.684385	\N	f
12	event_13_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento de Prueba 1743733832	2025-04-04 02:30:35.616584	\N	f
13	event_14_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento para Mañana 1743733836	2025-04-04 02:30:37.918889	\N	f
17	event_18_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento para Próxima Semana 1743734622	2025-04-04 02:43:43.230919	\N	f
15	event_16_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento de Prueba 1743734615	2025-04-04 02:43:38.68216	\N	f
16	event_17_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento para Mañana 1743734619	2025-04-04 02:43:41.143317	\N	f
18	event_19_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento para Pruebas de Participación 1743734627	2025-04-04 02:43:48.858195	\N	f
21	event_22_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento para Próxima Semana 1743734730	2025-04-04 02:45:31.62561	\N	f
19	event_20_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento de Prueba 1743734723	2025-04-04 02:45:26.882554	\N	f
20	event_21_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento para Mañana 1743734728	2025-04-04 02:45:29.574422	\N	f
22	event_23_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento para Pruebas de Participación 1743734736	2025-04-04 02:45:37.269386	\N	f
25	event_26_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento para Próxima Semana 1743735006	2025-04-04 02:50:07.231941	\N	f
23	event_24_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento de Prueba 1743735000	2025-04-04 02:50:02.935092	\N	f
24	event_25_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento para Mañana 1743735003	2025-04-04 02:50:05.37216	\N	f
26	event_27_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento para Pruebas de Participación 1743735011	2025-04-04 02:50:12.602173	\N	f
29	event_30_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento para Próxima Semana 1743735041	2025-04-04 02:50:42.070331	\N	f
27	event_28_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento de Prueba 1743735035	2025-04-04 02:50:38.078312	\N	f
28	event_29_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento para Mañana 1743735039	2025-04-04 02:50:40.399393	\N	f
30	event_31_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento para Pruebas de Participación 1743735047	2025-04-04 02:50:47.934542	\N	f
33	event_34_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento para Próxima Semana 1743735108	2025-04-04 02:51:49.647328	\N	f
31	event_32_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento de Prueba 1743735102	2025-04-04 02:51:45.554354	\N	f
32	event_33_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento para Mañana 1743735106	2025-04-04 02:51:47.914701	\N	f
34	event_35_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento para Pruebas de Participación 1743735115	2025-04-04 02:51:56.017795	\N	f
35	event_36_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento de Prueba 1743736586	2025-04-04 03:16:27.499707	\N	f
36	event_37_auth0_67d5d64d64ccf1c522a6950b	messaging	Evento Evento de Prueba 1743736594	2025-04-04 03:16:34.988438	\N	f
37	dm_7_auth0_67ef66dfcb9e2a66485f2dde	messaging	Chat auth0_67ef66dfc-7	2025-04-06 15:00:00.666232	\N	t
38	room_Sala-2504061100_auth0_67ef66dfcb9e2a66485f2dde	messaging	Sala-2504061100	2025-04-06 15:00:11.036827	\N	f
40	room_Sala-2504061109_auth0_67ef66dfcb9e2a66485f2dde	messaging	Sala-2504061109	2025-04-06 15:09:39.617128	\N	f
41	event_38_310898ae	messaging	Evento Test Event 20250409003324	2025-04-09 04:33:25.937821	\N	f
42	event_39_310898ae	messaging	Evento Test Event 20250409003431	2025-04-09 04:34:33.000222	\N	f
43	event_40_310898ae	messaging	Evento Test Event 20250409003455	2025-04-09 04:34:57.437854	\N	f
44	event_41_310898ae	messaging	Evento Test Event 20250409003629	2025-04-09 04:36:30.938143	\N	f
45	event_42_310898ae	messaging	Evento Test Event 20250409003907	2025-04-09 04:39:08.649035	\N	f
46	event_43_310898ae	messaging	Evento Test Event 20250409010849	2025-04-09 05:08:51.49311	\N	f
47	event_44_aa86674e	messaging	Evento Test Event 20250409011905	2025-04-09 05:19:07.337625	44	f
48	event_45_310898ae	messaging	Evento Evento de prueba automatización	2025-04-09 07:20:59.372719	45	f
49	event_46_310898ae	messaging	Evento Carrera Parque Cespedes	2025-04-11 02:40:50.215784	46	f
50	event_47_a87ff679	messaging	Evento Paque de la Libertad	2025-04-11 03:38:18.516916	\N	f
51	event_48_a87ff679	messaging	Evento Carrera	2025-04-11 04:05:13.409052	\N	f
52	event_50_a87ff679	messaging	Evento Carrera	2025-04-11 04:15:19.724533	\N	f
53	event_51_a87ff679	messaging	Evento Runner	2025-04-11 05:10:16.737126	51	f
\.


--
-- Data for Name: class; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.class (id, name, description, duration, max_capacity, difficulty_level, category_id, category_enum, is_active, created_at, updated_at, created_by, gym_id) FROM stdin;
98	Clase de Prueba 1744182191 (Actualizada)	Esta es una clase creada automáticamente para pruebas de integración - Esta descripción fue actualizada	60	25	INTERMEDIATE	\N	\N	f	2025-04-09 07:03:12.174931+00	2025-04-09 07:03:16.575272+00	4	1
2	Muay Thai	Muay Thai Class	60	30	INTERMEDIATE	\N	OTHER	t	2025-04-03 03:17:33.257909+00	\N	\N	1
36	Yoga Flow	Clase de yoga fluido para todos los niveles	60	15	INTERMEDIATE	\N	OTHER	f	2025-04-04 22:36:18.867194+00	2025-04-04 22:37:32.830856+00	\N	1
37	CrossFit Training	Entrenamiento funcional de alta intensidad	45	12	ADVANCED	\N	OTHER	f	2025-04-04 22:36:20.067969+00	2025-04-04 22:37:33.576706+00	\N	1
38	Pilates Mat	Clase de pilates en colchoneta para fortalecer core	55	20	BEGINNER	\N	OTHER	f	2025-04-04 22:36:20.709824+00	2025-04-04 22:37:34.365939+00	\N	1
39	Spinning Power	Clase de ciclismo indoor de alta intensidad	45	25	INTERMEDIATE	\N	OTHER	f	2025-04-04 22:36:21.406362+00	2025-04-04 22:37:35.224206+00	\N	1
40	Box Training	Entrenamiento de boxeo para principiantes y nivel medio	60	15	INTERMEDIATE	\N	OTHER	f	2025-04-04 22:36:22.04829+00	2025-04-04 22:37:36.03948+00	\N	1
17	Clase de prueba con fix	Clase para probar la solución del gym_id	60	10	INTERMEDIATE	\N	OTHER	f	2025-04-04 05:15:36.731789+00	2025-04-04 05:15:39.760586+00	\N	1
18	Clase de prueba con fix	Clase para probar la solución del gym_id	60	10	INTERMEDIATE	\N	OTHER	t	2025-04-04 22:19:58.266086+00	\N	\N	1
26	Yoga Flow	Clase de yoga fluido para todos los niveles	60	15	INTERMEDIATE	\N	OTHER	t	2025-04-04 22:32:43.9782+00	\N	\N	1
27	CrossFit Training	Entrenamiento funcional de alta intensidad	45	12	ADVANCED	\N	OTHER	t	2025-04-04 22:32:44.730746+00	\N	\N	1
28	Pilates Mat	Clase de pilates en colchoneta para fortalecer core	55	20	BEGINNER	\N	OTHER	t	2025-04-04 22:32:45.400348+00	\N	\N	1
29	Spinning Power	Clase de ciclismo indoor de alta intensidad	45	25	INTERMEDIATE	\N	OTHER	t	2025-04-04 22:32:46.096199+00	\N	\N	1
30	Box Training	Entrenamiento de boxeo para principiantes y nivel medio	60	15	INTERMEDIATE	\N	OTHER	t	2025-04-04 22:32:46.825498+00	\N	\N	1
31	Yoga Flow	Clase de yoga fluido para todos los niveles	60	15	INTERMEDIATE	\N	OTHER	f	2025-04-04 22:34:29.03043+00	2025-04-04 22:35:43.388955+00	\N	1
32	CrossFit Training	Entrenamiento funcional de alta intensidad	45	12	ADVANCED	\N	OTHER	f	2025-04-04 22:34:30.311035+00	2025-04-04 22:35:44.200536+00	\N	1
33	Pilates Mat	Clase de pilates en colchoneta para fortalecer core	55	20	BEGINNER	\N	OTHER	f	2025-04-04 22:34:30.989538+00	2025-04-04 22:35:45.009992+00	\N	1
34	Spinning Power	Clase de ciclismo indoor de alta intensidad	45	25	INTERMEDIATE	\N	OTHER	f	2025-04-04 22:34:31.679433+00	2025-04-04 22:35:45.736466+00	\N	1
35	Box Training	Entrenamiento de boxeo para principiantes y nivel medio	60	15	INTERMEDIATE	\N	OTHER	f	2025-04-04 22:34:32.371298+00	2025-04-04 22:35:46.531647+00	\N	1
43	Clase de Prueba 1743952959 (Actualizada)	Esta es una clase creada automáticamente para pruebas de integración - Esta descripción fue actualizada	60	25	INTERMEDIATE	\N	OTHER	t	2025-04-06 15:22:40.092099+00	2025-04-06 15:22:41.81226+00	\N	1
54	Clase de Prueba 1744088128 (Actualizada)	Esta es una clase creada automáticamente para pruebas de integración - Esta descripción fue actualizada	60	25	INTERMEDIATE	\N	OTHER	f	2025-04-08 04:55:28.869614+00	2025-04-08 04:55:32.530187+00	\N	1
44	Clase de Prueba 1743953057 (Actualizada)	Esta es una clase creada automáticamente para pruebas de integración - Esta descripción fue actualizada	60	25	INTERMEDIATE	\N	OTHER	f	2025-04-06 15:24:17.256474+00	2025-04-06 15:24:22.896387+00	\N	1
45	Clase de Prueba 1743953161 (Actualizada)	Esta es una clase creada automáticamente para pruebas de integración - Esta descripción fue actualizada	60	25	INTERMEDIATE	\N	OTHER	f	2025-04-06 15:26:01.661128+00	2025-04-06 15:26:08.69558+00	\N	1
48	Clase de prueba sesiones	Clase para probar la creación de sesiones	60	10	INTERMEDIATE	\N	OTHER	f	2025-04-06 15:29:05.69425+00	2025-04-06 15:29:11.639115+00	\N	1
49	Yoga Flow	Clase de yoga fluido para todos los niveles	60	15	INTERMEDIATE	\N	OTHER	f	2025-04-06 15:30:59.048582+00	2025-04-06 15:32:53.218168+00	\N	1
50	CrossFit Training	Entrenamiento funcional de alta intensidad	45	12	ADVANCED	\N	OTHER	f	2025-04-06 15:31:00.783845+00	2025-04-06 15:32:54.888124+00	\N	1
51	Pilates Mat	Clase de pilates en colchoneta para fortalecer core	55	20	BEGINNER	\N	OTHER	f	2025-04-06 15:31:01.753846+00	2025-04-06 15:32:55.973252+00	\N	1
52	Spinning Power	Clase de ciclismo indoor de alta intensidad	45	25	INTERMEDIATE	\N	OTHER	f	2025-04-06 15:31:02.738862+00	2025-04-06 15:32:57.073551+00	\N	1
53	Box Training	Entrenamiento de boxeo para principiantes y nivel medio	60	15	INTERMEDIATE	\N	OTHER	f	2025-04-06 15:31:03.733897+00	2025-04-06 15:32:58.173516+00	\N	1
60	Clase de prueba sesiones	Clase para probar la creación de sesiones	60	10	INTERMEDIATE	\N	OTHER	f	2025-04-08 04:57:32.79462+00	2025-04-08 04:57:37.225244+00	\N	1
55	Yoga Flow	Clase de yoga fluido para todos los niveles	60	15	INTERMEDIATE	\N	OTHER	f	2025-04-08 04:56:19.678041+00	2025-04-08 04:57:42.195619+00	\N	1
56	CrossFit Training	Entrenamiento funcional de alta intensidad	45	12	ADVANCED	\N	OTHER	f	2025-04-08 04:56:20.99967+00	2025-04-08 04:57:43.060393+00	\N	1
57	Pilates Mat	Clase de pilates en colchoneta para fortalecer core	55	20	BEGINNER	\N	OTHER	f	2025-04-08 04:56:21.827181+00	2025-04-08 04:57:43.854218+00	\N	1
58	Spinning Power	Clase de ciclismo indoor de alta intensidad	45	25	INTERMEDIATE	\N	OTHER	f	2025-04-08 04:56:22.446683+00	2025-04-08 04:57:44.627831+00	\N	1
59	Box Training	Entrenamiento de boxeo para principiantes y nivel medio	60	15	INTERMEDIATE	\N	OTHER	f	2025-04-08 04:56:23.123617+00	2025-04-08 04:57:45.328707+00	\N	1
63	Clase de Prueba 1744176714	Esta es una clase creada automáticamente para pruebas de integración	60	20	INTERMEDIATE	\N	OTHER	t	2025-04-09 05:31:55.014336+00	\N	\N	1
64	Clase de Prueba 1744177569	Esta es una clase creada automáticamente para pruebas de integración	60	20	INTERMEDIATE	\N	OTHER	t	2025-04-09 05:46:10.030108+00	\N	\N	1
65	Clase de Prueba 1744177687	Esta es una clase creada automáticamente para pruebas de integración	60	20	INTERMEDIATE	\N	OTHER	t	2025-04-09 05:48:08.07376+00	\N	\N	1
101	Yoga Flow	Clase de yoga fluido para todos los niveles	60	15	INTERMEDIATE	\N	\N	f	2025-04-09 07:05:40.640002+00	2025-04-09 07:07:30.430867+00	4	1
102	CrossFit Training	Entrenamiento funcional de alta intensidad	45	12	ADVANCED	\N	\N	f	2025-04-09 07:05:41.856339+00	2025-04-09 07:07:31.567962+00	4	1
103	Pilates Mat	Clase de pilates en colchoneta para fortalecer core	55	20	BEGINNER	\N	\N	f	2025-04-09 07:05:42.9464+00	2025-04-09 07:07:32.66469+00	4	1
104	Spinning Power	Clase de ciclismo indoor de alta intensidad	45	25	INTERMEDIATE	\N	\N	f	2025-04-09 07:05:44.155314+00	2025-04-09 07:07:33.768392+00	4	1
105	Box Training	Entrenamiento de boxeo para principiantes y nivel medio	60	15	INTERMEDIATE	\N	\N	f	2025-04-09 07:05:45.09199+00	2025-04-09 07:07:34.960263+00	4	1
\.


--
-- Data for Name: class_category_custom; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.class_category_custom (id, name, description, color, icon, is_active, created_at, updated_at, created_by, gym_id) FROM stdin;
\.


--
-- Data for Name: class_participation; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.class_participation (id, session_id, member_id, status, registration_time, attendance_time, cancellation_time, cancellation_reason, created_at, updated_at, gym_id) FROM stdin;
\.


--
-- Data for Name: class_session; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.class_session (id, class_id, trainer_id, start_time, end_time, room, is_recurring, recurrence_pattern, status, current_participants, notes, created_at, updated_at, created_by, gym_id) FROM stdin;
50	17	6	2025-04-05 10:00:00.299484	2025-04-05 11:00:00.299502	\N	f	\N	SCHEDULED	0	\N	2025-04-04 05:15:38.449395+00	\N	\N	1
96	28	6	2025-04-07 09:00:00	2025-04-07 09:55:00	\N	f	\N	SCHEDULED	0	Sesión de Pilates Mat - Monday 09:00	2025-04-04 22:32:48.475136+00	\N	\N	1
97	27	6	2025-04-07 13:00:00	2025-04-07 13:45:00	\N	f	\N	SCHEDULED	0	Sesión de CrossFit Training - Monday 13:00	2025-04-04 22:32:49.344451+00	\N	\N	1
98	29	6	2025-04-07 13:00:00	2025-04-07 13:45:00	\N	f	\N	SCHEDULED	0	Sesión de Spinning Power - Monday 13:00	2025-04-04 22:32:50.277447+00	\N	\N	1
99	30	6	2025-04-07 18:30:00	2025-04-07 19:30:00	\N	f	\N	SCHEDULED	0	Sesión de Box Training - Monday 18:30	2025-04-04 22:32:51.166825+00	\N	\N	1
100	26	6	2025-04-07 18:30:00	2025-04-07 19:30:00	\N	f	\N	SCHEDULED	0	Sesión de Yoga Flow - Monday 18:30	2025-04-04 22:32:52.020632+00	\N	\N	1
101	28	6	2025-04-08 08:30:00	2025-04-08 09:25:00	\N	f	\N	SCHEDULED	0	Sesión de Pilates Mat - Tuesday 08:30	2025-04-04 22:32:52.91314+00	\N	\N	1
102	29	6	2025-04-08 08:30:00	2025-04-08 09:15:00	\N	f	\N	SCHEDULED	0	Sesión de Spinning Power - Tuesday 08:30	2025-04-04 22:32:53.854132+00	\N	\N	1
103	26	6	2025-04-08 14:00:00	2025-04-08 15:00:00	\N	f	\N	SCHEDULED	0	Sesión de Yoga Flow - Tuesday 14:00	2025-04-04 22:32:54.657564+00	\N	\N	1
104	30	6	2025-04-08 14:00:00	2025-04-08 15:00:00	\N	f	\N	SCHEDULED	0	Sesión de Box Training - Tuesday 14:00	2025-04-04 22:32:55.59288+00	\N	\N	1
105	27	6	2025-04-08 19:00:00	2025-04-08 19:45:00	\N	f	\N	SCHEDULED	0	Sesión de CrossFit Training - Tuesday 19:00	2025-04-04 22:32:56.506305+00	\N	\N	1
106	28	6	2025-04-08 19:00:00	2025-04-08 19:55:00	\N	f	\N	SCHEDULED	0	Sesión de Pilates Mat - Tuesday 19:00	2025-04-04 22:32:57.388379+00	\N	\N	1
107	27	6	2025-04-09 09:00:00	2025-04-09 09:45:00	\N	f	\N	SCHEDULED	0	Sesión de CrossFit Training - Wednesday 09:00	2025-04-04 22:32:58.2494+00	\N	\N	1
108	26	6	2025-04-09 09:00:00	2025-04-09 10:00:00	\N	f	\N	SCHEDULED	0	Sesión de Yoga Flow - Wednesday 09:00	2025-04-04 22:32:59.136032+00	\N	\N	1
109	30	6	2025-04-09 13:00:00	2025-04-09 14:00:00	\N	f	\N	SCHEDULED	0	Sesión de Box Training - Wednesday 13:00	2025-04-04 22:33:00.117667+00	\N	\N	1
110	29	6	2025-04-09 13:00:00	2025-04-09 13:45:00	\N	f	\N	SCHEDULED	0	Sesión de Spinning Power - Wednesday 13:00	2025-04-04 22:33:00.989184+00	\N	\N	1
111	28	6	2025-04-09 18:30:00	2025-04-09 19:25:00	\N	f	\N	SCHEDULED	0	Sesión de Pilates Mat - Wednesday 18:30	2025-04-04 22:33:01.912977+00	\N	\N	1
112	27	6	2025-04-09 18:30:00	2025-04-09 19:15:00	\N	f	\N	SCHEDULED	0	Sesión de CrossFit Training - Wednesday 18:30	2025-04-04 22:33:03.026906+00	\N	\N	1
113	26	6	2025-04-10 08:30:00	2025-04-10 09:30:00	\N	f	\N	SCHEDULED	0	Sesión de Yoga Flow - Thursday 08:30	2025-04-04 22:33:03.885804+00	\N	\N	1
114	30	6	2025-04-10 08:30:00	2025-04-10 09:30:00	\N	f	\N	SCHEDULED	0	Sesión de Box Training - Thursday 08:30	2025-04-04 22:33:04.718576+00	\N	\N	1
115	29	6	2025-04-10 14:00:00	2025-04-10 14:45:00	\N	f	\N	SCHEDULED	0	Sesión de Spinning Power - Thursday 14:00	2025-04-04 22:33:05.595976+00	\N	\N	1
116	28	6	2025-04-10 14:00:00	2025-04-10 14:55:00	\N	f	\N	SCHEDULED	0	Sesión de Pilates Mat - Thursday 14:00	2025-04-04 22:33:06.491576+00	\N	\N	1
117	27	6	2025-04-10 19:00:00	2025-04-10 19:45:00	\N	f	\N	SCHEDULED	0	Sesión de CrossFit Training - Thursday 19:00	2025-04-04 22:33:07.336091+00	\N	\N	1
118	26	6	2025-04-10 19:00:00	2025-04-10 20:00:00	\N	f	\N	SCHEDULED	0	Sesión de Yoga Flow - Thursday 19:00	2025-04-04 22:33:08.155511+00	\N	\N	1
119	28	6	2025-04-11 09:00:00	2025-04-11 09:55:00	\N	f	\N	SCHEDULED	0	Sesión de Pilates Mat - Friday 09:00	2025-04-04 22:33:09.049436+00	\N	\N	1
120	29	6	2025-04-11 09:00:00	2025-04-11 09:45:00	\N	f	\N	SCHEDULED	0	Sesión de Spinning Power - Friday 09:00	2025-04-04 22:33:09.903813+00	\N	\N	1
121	26	6	2025-04-11 13:00:00	2025-04-11 14:00:00	\N	f	\N	SCHEDULED	0	Sesión de Yoga Flow - Friday 13:00	2025-04-04 22:33:10.733502+00	\N	\N	1
122	27	6	2025-04-11 13:00:00	2025-04-11 13:45:00	\N	f	\N	SCHEDULED	0	Sesión de CrossFit Training - Friday 13:00	2025-04-04 22:33:11.764276+00	\N	\N	1
123	30	6	2025-04-11 18:30:00	2025-04-11 19:30:00	\N	f	\N	SCHEDULED	0	Sesión de Box Training - Friday 18:30	2025-04-04 22:33:12.585036+00	\N	\N	1
124	28	6	2025-04-11 18:30:00	2025-04-11 19:25:00	\N	f	\N	SCHEDULED	0	Sesión de Pilates Mat - Friday 18:30	2025-04-04 22:33:13.430502+00	\N	\N	1
125	26	6	2025-04-12 10:00:00	2025-04-12 11:00:00	\N	f	\N	SCHEDULED	0	Sesión de Yoga Flow - Saturday 10:00	2025-04-04 22:33:14.266184+00	\N	\N	1
126	27	6	2025-04-12 10:00:00	2025-04-12 10:45:00	\N	f	\N	SCHEDULED	0	Sesión de CrossFit Training - Saturday 10:00	2025-04-04 22:33:15.148838+00	\N	\N	1
127	29	6	2025-04-12 12:00:00	2025-04-12 12:45:00	\N	f	\N	SCHEDULED	0	Sesión de Spinning Power - Saturday 12:00	2025-04-04 22:33:15.995705+00	\N	\N	1
128	30	6	2025-04-12 12:00:00	2025-04-12 13:00:00	\N	f	\N	SCHEDULED	0	Sesión de Box Training - Saturday 12:00	2025-04-04 22:33:16.888253+00	\N	\N	1
129	28	6	2025-04-12 17:00:00	2025-04-12 17:55:00	\N	f	\N	SCHEDULED	0	Sesión de Pilates Mat - Saturday 17:00	2025-04-04 22:33:17.839874+00	\N	\N	1
130	26	6	2025-04-12 17:00:00	2025-04-12 18:00:00	\N	f	\N	SCHEDULED	0	Sesión de Yoga Flow - Saturday 17:00	2025-04-04 22:33:18.643389+00	\N	\N	1
131	26	6	2025-04-13 10:00:00	2025-04-13 11:00:00	\N	f	\N	SCHEDULED	0	Sesión de Yoga Flow - Sunday 10:00	2025-04-04 22:33:19.501593+00	\N	\N	1
132	28	6	2025-04-13 10:00:00	2025-04-13 10:55:00	\N	f	\N	SCHEDULED	0	Sesión de Pilates Mat - Sunday 10:00	2025-04-04 22:33:20.463552+00	\N	\N	1
133	27	6	2025-04-13 12:00:00	2025-04-13 12:45:00	\N	f	\N	SCHEDULED	0	Sesión de CrossFit Training - Sunday 12:00	2025-04-04 22:33:21.371848+00	\N	\N	1
134	29	6	2025-04-13 12:00:00	2025-04-13 12:45:00	\N	f	\N	SCHEDULED	0	Sesión de Spinning Power - Sunday 12:00	2025-04-04 22:33:22.203034+00	\N	\N	1
135	30	6	2025-04-13 16:00:00	2025-04-13 17:00:00	\N	f	\N	SCHEDULED	0	Sesión de Box Training - Sunday 16:00	2025-04-04 22:33:23.061181+00	\N	\N	1
136	26	6	2025-04-13 16:00:00	2025-04-13 17:00:00	\N	f	\N	SCHEDULED	0	Sesión de Yoga Flow - Sunday 16:00	2025-04-04 22:33:24.007404+00	\N	\N	1
95	26	6	2025-04-07 09:00:00	2025-04-07 10:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Monday 09:00	2025-04-04 22:32:47.52269+00	2025-04-04 22:33:25.210614+00	\N	1
141	35	6	2025-04-07 18:30:00	2025-04-07 19:30:00	\N	f	\N	CANCELLED	0	Sesión de Box Training - Monday 18:30	2025-04-04 22:34:36.501721+00	2025-04-04 22:35:16.461489+00	\N	1
138	33	6	2025-04-07 09:00:00	2025-04-07 09:55:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Monday 09:00	2025-04-04 22:34:33.87514+00	2025-04-04 22:35:14.360087+00	\N	1
140	34	6	2025-04-07 13:00:00	2025-04-07 13:45:00	\N	f	\N	CANCELLED	0	¡Clase especial! Traer equipo adicional.	2025-04-04 22:34:35.607732+00	2025-04-04 22:35:15.740297+00	\N	1
142	31	6	2025-04-07 18:30:00	2025-04-07 19:30:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Monday 18:30	2025-04-04 22:34:37.344904+00	2025-04-04 22:35:17.279187+00	\N	1
143	33	6	2025-04-08 08:30:00	2025-04-08 09:25:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Tuesday 08:30	2025-04-04 22:34:38.161891+00	2025-04-04 22:35:18.021372+00	\N	1
144	34	6	2025-04-08 08:30:00	2025-04-08 09:15:00	\N	f	\N	CANCELLED	0	Sesión de Spinning Power - Tuesday 08:30	2025-04-04 22:34:39.337924+00	2025-04-04 22:35:18.67225+00	\N	1
145	31	6	2025-04-08 14:00:00	2025-04-08 15:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Tuesday 14:00	2025-04-04 22:34:40.177353+00	2025-04-04 22:35:19.382936+00	\N	1
146	35	6	2025-04-08 14:00:00	2025-04-08 15:00:00	\N	f	\N	CANCELLED	0	Sesión de Box Training - Tuesday 14:00	2025-04-04 22:34:41.169358+00	2025-04-04 22:35:20.17777+00	\N	1
147	32	6	2025-04-08 19:00:00	2025-04-08 19:45:00	\N	f	\N	CANCELLED	0	Sesión de CrossFit Training - Tuesday 19:00	2025-04-04 22:34:42.118014+00	2025-04-04 22:35:21.063176+00	\N	1
148	33	6	2025-04-08 19:00:00	2025-04-08 19:55:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Tuesday 19:00	2025-04-04 22:34:43.027781+00	2025-04-04 22:35:21.708886+00	\N	1
149	32	6	2025-04-09 09:00:00	2025-04-09 09:45:00	\N	f	\N	CANCELLED	0	Sesión de CrossFit Training - Wednesday 09:00	2025-04-04 22:34:43.899968+00	2025-04-04 22:35:22.416594+00	\N	1
150	31	6	2025-04-09 09:00:00	2025-04-09 10:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Wednesday 09:00	2025-04-04 22:34:44.819408+00	2025-04-04 22:35:23.054654+00	\N	1
137	31	6	2025-04-07 09:00:00	2025-04-07 10:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Monday 09:00	2025-04-04 22:34:33.06567+00	2025-04-04 22:35:11.140269+00	\N	1
139	32	6	2025-04-07 13:00:00	2025-04-07 13:45:00	\N	f	\N	CANCELLED	0	Sesión de CrossFit Training - Monday 13:00	2025-04-04 22:34:34.695104+00	2025-04-04 22:35:15.11135+00	\N	1
151	35	6	2025-04-09 13:00:00	2025-04-09 14:00:00	\N	f	\N	CANCELLED	0	Sesión de Box Training - Wednesday 13:00	2025-04-04 22:34:45.679765+00	2025-04-04 22:35:23.6967+00	\N	1
152	34	6	2025-04-09 13:00:00	2025-04-09 13:45:00	\N	f	\N	CANCELLED	0	Sesión de Spinning Power - Wednesday 13:00	2025-04-04 22:34:46.49681+00	2025-04-04 22:35:24.381902+00	\N	1
153	33	6	2025-04-09 18:30:00	2025-04-09 19:25:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Wednesday 18:30	2025-04-04 22:34:47.458923+00	2025-04-04 22:35:25.026069+00	\N	1
154	32	6	2025-04-09 18:30:00	2025-04-09 19:15:00	\N	f	\N	CANCELLED	0	Sesión de CrossFit Training - Wednesday 18:30	2025-04-04 22:34:48.393918+00	2025-04-04 22:35:25.720291+00	\N	1
155	31	6	2025-04-10 08:30:00	2025-04-10 09:30:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Thursday 08:30	2025-04-04 22:34:49.263495+00	2025-04-04 22:35:26.469124+00	\N	1
156	35	6	2025-04-10 08:30:00	2025-04-10 09:30:00	\N	f	\N	CANCELLED	0	Sesión de Box Training - Thursday 08:30	2025-04-04 22:34:50.153708+00	2025-04-04 22:35:27.180646+00	\N	1
157	34	6	2025-04-10 14:00:00	2025-04-10 14:45:00	\N	f	\N	CANCELLED	0	Sesión de Spinning Power - Thursday 14:00	2025-04-04 22:34:51.005237+00	2025-04-04 22:35:27.827807+00	\N	1
158	33	6	2025-04-10 14:00:00	2025-04-10 14:55:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Thursday 14:00	2025-04-04 22:34:51.803261+00	2025-04-04 22:35:28.541719+00	\N	1
159	32	6	2025-04-10 19:00:00	2025-04-10 19:45:00	\N	f	\N	CANCELLED	0	Sesión de CrossFit Training - Thursday 19:00	2025-04-04 22:34:52.607441+00	2025-04-04 22:35:29.322447+00	\N	1
160	31	6	2025-04-10 19:00:00	2025-04-10 20:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Thursday 19:00	2025-04-04 22:34:53.482026+00	2025-04-04 22:35:30.14697+00	\N	1
161	33	6	2025-04-11 09:00:00	2025-04-11 09:55:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Friday 09:00	2025-04-04 22:34:54.358054+00	2025-04-04 22:35:30.773145+00	\N	1
162	34	6	2025-04-11 09:00:00	2025-04-11 09:45:00	\N	f	\N	CANCELLED	0	Sesión de Spinning Power - Friday 09:00	2025-04-04 22:34:55.22612+00	2025-04-04 22:35:31.467418+00	\N	1
163	31	6	2025-04-11 13:00:00	2025-04-11 14:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Friday 13:00	2025-04-04 22:34:56.182873+00	2025-04-04 22:35:32.309101+00	\N	1
164	32	6	2025-04-11 13:00:00	2025-04-11 13:45:00	\N	f	\N	CANCELLED	0	Sesión de CrossFit Training - Friday 13:00	2025-04-04 22:34:57.133707+00	2025-04-04 22:35:33.164978+00	\N	1
165	35	6	2025-04-11 18:30:00	2025-04-11 19:30:00	\N	f	\N	CANCELLED	0	Sesión de Box Training - Friday 18:30	2025-04-04 22:34:57.991779+00	2025-04-04 22:35:33.816546+00	\N	1
166	33	6	2025-04-11 18:30:00	2025-04-11 19:25:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Friday 18:30	2025-04-04 22:34:58.936044+00	2025-04-04 22:35:34.474971+00	\N	1
167	31	6	2025-04-12 10:00:00	2025-04-12 11:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Saturday 10:00	2025-04-04 22:35:00.036303+00	2025-04-04 22:35:35.194546+00	\N	1
168	32	6	2025-04-12 10:00:00	2025-04-12 10:45:00	\N	f	\N	CANCELLED	0	Sesión de CrossFit Training - Saturday 10:00	2025-04-04 22:35:00.935577+00	2025-04-04 22:35:35.9586+00	\N	1
169	34	6	2025-04-12 12:00:00	2025-04-12 12:45:00	\N	f	\N	CANCELLED	0	Sesión de Spinning Power - Saturday 12:00	2025-04-04 22:35:01.754897+00	2025-04-04 22:35:36.599573+00	\N	1
170	35	6	2025-04-12 12:00:00	2025-04-12 13:00:00	\N	f	\N	CANCELLED	0	Sesión de Box Training - Saturday 12:00	2025-04-04 22:35:02.551668+00	2025-04-04 22:35:37.297727+00	\N	1
171	33	6	2025-04-12 17:00:00	2025-04-12 17:55:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Saturday 17:00	2025-04-04 22:35:03.488261+00	2025-04-04 22:35:38.014284+00	\N	1
172	31	6	2025-04-12 17:00:00	2025-04-12 18:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Saturday 17:00	2025-04-04 22:35:04.322392+00	2025-04-04 22:35:38.719015+00	\N	1
173	31	6	2025-04-13 10:00:00	2025-04-13 11:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Sunday 10:00	2025-04-04 22:35:05.207401+00	2025-04-04 22:35:39.395387+00	\N	1
174	33	6	2025-04-13 10:00:00	2025-04-13 10:55:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Sunday 10:00	2025-04-04 22:35:06.159023+00	2025-04-04 22:35:40.113531+00	\N	1
175	32	6	2025-04-13 12:00:00	2025-04-13 12:45:00	\N	f	\N	CANCELLED	0	Sesión de CrossFit Training - Sunday 12:00	2025-04-04 22:35:07.034385+00	2025-04-04 22:35:40.769583+00	\N	1
176	34	6	2025-04-13 12:00:00	2025-04-13 12:45:00	\N	f	\N	CANCELLED	0	Sesión de Spinning Power - Sunday 12:00	2025-04-04 22:35:07.897779+00	2025-04-04 22:35:41.39205+00	\N	1
177	35	6	2025-04-13 16:00:00	2025-04-13 17:00:00	\N	f	\N	CANCELLED	0	Sesión de Box Training - Sunday 16:00	2025-04-04 22:35:08.909087+00	2025-04-04 22:35:42.072899+00	\N	1
178	31	6	2025-04-13 16:00:00	2025-04-13 17:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Sunday 16:00	2025-04-04 22:35:09.713347+00	2025-04-04 22:35:42.708811+00	\N	1
183	40	6	2025-04-07 18:30:00	2025-04-07 19:30:00	\N	f	\N	CANCELLED	0	Sesión de Box Training - Monday 18:30	2025-04-04 22:36:26.198947+00	2025-04-04 22:37:06.183933+00	\N	1
180	38	6	2025-04-07 09:00:00	2025-04-07 09:55:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Monday 09:00	2025-04-04 22:36:23.567809+00	2025-04-04 22:37:04.164802+00	\N	1
181	37	6	2025-04-07 13:00:00	2025-04-07 13:45:00	\N	f	\N	CANCELLED	0	Sesión de CrossFit Training - Monday 13:00	2025-04-04 22:36:24.456471+00	2025-04-04 22:37:04.817195+00	\N	1
182	39	6	2025-04-07 13:00:00	2025-04-07 13:45:00	\N	f	\N	CANCELLED	0	¡Clase especial! Traer equipo adicional.	2025-04-04 22:36:25.301899+00	2025-04-04 22:37:05.473271+00	\N	1
184	36	6	2025-04-07 18:30:00	2025-04-07 19:30:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Monday 18:30	2025-04-04 22:36:27.110833+00	2025-04-04 22:37:06.825806+00	\N	1
185	38	6	2025-04-08 08:30:00	2025-04-08 09:25:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Tuesday 08:30	2025-04-04 22:36:27.97729+00	2025-04-04 22:37:07.541058+00	\N	1
186	39	6	2025-04-08 08:30:00	2025-04-08 09:15:00	\N	f	\N	CANCELLED	0	Sesión de Spinning Power - Tuesday 08:30	2025-04-04 22:36:28.859177+00	2025-04-04 22:37:08.199439+00	\N	1
187	36	6	2025-04-08 14:00:00	2025-04-08 15:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Tuesday 14:00	2025-04-04 22:36:29.778645+00	2025-04-04 22:37:08.872785+00	\N	1
189	37	6	2025-04-08 19:00:00	2025-04-08 19:45:00	\N	f	\N	CANCELLED	0	Sesión de CrossFit Training - Tuesday 19:00	2025-04-04 22:36:31.511343+00	2025-04-04 22:37:10.219399+00	\N	1
190	38	6	2025-04-08 19:00:00	2025-04-08 19:55:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Tuesday 19:00	2025-04-04 22:36:32.324774+00	2025-04-04 22:37:10.854515+00	\N	1
191	37	6	2025-04-09 09:00:00	2025-04-09 09:45:00	\N	f	\N	CANCELLED	0	Sesión de CrossFit Training - Wednesday 09:00	2025-04-04 22:36:33.313691+00	2025-04-04 22:37:11.603431+00	\N	1
192	36	6	2025-04-09 09:00:00	2025-04-09 10:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Wednesday 09:00	2025-04-04 22:36:34.171676+00	2025-04-04 22:37:12.305092+00	\N	1
193	40	6	2025-04-09 13:00:00	2025-04-09 14:00:00	\N	f	\N	CANCELLED	0	Sesión de Box Training - Wednesday 13:00	2025-04-04 22:36:35.026225+00	2025-04-04 22:37:12.940528+00	\N	1
194	39	6	2025-04-09 13:00:00	2025-04-09 13:45:00	\N	f	\N	CANCELLED	0	Sesión de Spinning Power - Wednesday 13:00	2025-04-04 22:36:35.933517+00	2025-04-04 22:37:13.614391+00	\N	1
195	38	6	2025-04-09 18:30:00	2025-04-09 19:25:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Wednesday 18:30	2025-04-04 22:36:36.764679+00	2025-04-04 22:37:14.304972+00	\N	1
196	37	6	2025-04-09 18:30:00	2025-04-09 19:15:00	\N	f	\N	CANCELLED	0	Sesión de CrossFit Training - Wednesday 18:30	2025-04-04 22:36:37.595877+00	2025-04-04 22:37:15.104645+00	\N	1
197	36	6	2025-04-10 08:30:00	2025-04-10 09:30:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Thursday 08:30	2025-04-04 22:36:38.463635+00	2025-04-04 22:37:15.776478+00	\N	1
198	40	6	2025-04-10 08:30:00	2025-04-10 09:30:00	\N	f	\N	CANCELLED	0	Sesión de Box Training - Thursday 08:30	2025-04-04 22:36:39.291068+00	2025-04-04 22:37:16.463968+00	\N	1
199	39	6	2025-04-10 14:00:00	2025-04-10 14:45:00	\N	f	\N	CANCELLED	0	Sesión de Spinning Power - Thursday 14:00	2025-04-04 22:36:40.077384+00	2025-04-04 22:37:17.209271+00	\N	1
201	37	6	2025-04-10 19:00:00	2025-04-10 19:45:00	\N	f	\N	CANCELLED	0	Sesión de CrossFit Training - Thursday 19:00	2025-04-04 22:36:41.863957+00	2025-04-04 22:37:18.572999+00	\N	1
202	36	6	2025-04-10 19:00:00	2025-04-10 20:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Thursday 19:00	2025-04-04 22:36:42.709296+00	2025-04-04 22:37:19.270966+00	\N	1
203	38	6	2025-04-11 09:00:00	2025-04-11 09:55:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Friday 09:00	2025-04-04 22:36:43.56744+00	2025-04-04 22:37:20.039343+00	\N	1
179	36	6	2025-04-07 09:00:00	2025-04-07 10:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Monday 09:00	2025-04-04 22:36:22.740243+00	2025-04-04 22:37:00.515431+00	\N	1
188	40	6	2025-04-08 14:00:00	2025-04-08 15:00:00	\N	f	\N	CANCELLED	0	Sesión de Box Training - Tuesday 14:00	2025-04-04 22:36:30.693008+00	2025-04-04 22:37:09.555768+00	\N	1
200	38	6	2025-04-10 14:00:00	2025-04-10 14:55:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Thursday 14:00	2025-04-04 22:36:40.904879+00	2025-04-04 22:37:17.906337+00	\N	1
204	39	6	2025-04-11 09:00:00	2025-04-11 09:45:00	\N	f	\N	CANCELLED	0	Sesión de Spinning Power - Friday 09:00	2025-04-04 22:36:44.461382+00	2025-04-04 22:37:20.8233+00	\N	1
205	36	6	2025-04-11 13:00:00	2025-04-11 14:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Friday 13:00	2025-04-04 22:36:45.41235+00	2025-04-04 22:37:21.482448+00	\N	1
206	37	6	2025-04-11 13:00:00	2025-04-11 13:45:00	\N	f	\N	CANCELLED	0	Sesión de CrossFit Training - Friday 13:00	2025-04-04 22:36:46.208277+00	2025-04-04 22:37:22.17963+00	\N	1
207	40	6	2025-04-11 18:30:00	2025-04-11 19:30:00	\N	f	\N	CANCELLED	0	Sesión de Box Training - Friday 18:30	2025-04-04 22:36:47.014714+00	2025-04-04 22:37:22.904767+00	\N	1
208	38	6	2025-04-11 18:30:00	2025-04-11 19:25:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Friday 18:30	2025-04-04 22:36:48.216247+00	2025-04-04 22:37:23.572712+00	\N	1
209	36	6	2025-04-12 10:00:00	2025-04-12 11:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Saturday 10:00	2025-04-04 22:36:49.025778+00	2025-04-04 22:37:24.291621+00	\N	1
210	37	6	2025-04-12 10:00:00	2025-04-12 10:45:00	\N	f	\N	CANCELLED	0	Sesión de CrossFit Training - Saturday 10:00	2025-04-04 22:36:49.873325+00	2025-04-04 22:37:25.02625+00	\N	1
211	39	6	2025-04-12 12:00:00	2025-04-12 12:45:00	\N	f	\N	CANCELLED	0	Sesión de Spinning Power - Saturday 12:00	2025-04-04 22:36:50.861574+00	2025-04-04 22:37:25.732501+00	\N	1
212	40	6	2025-04-12 12:00:00	2025-04-12 13:00:00	\N	f	\N	CANCELLED	0	Sesión de Box Training - Saturday 12:00	2025-04-04 22:36:51.758648+00	2025-04-04 22:37:26.460512+00	\N	1
213	38	6	2025-04-12 17:00:00	2025-04-12 17:55:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Saturday 17:00	2025-04-04 22:36:52.550126+00	2025-04-04 22:37:27.165195+00	\N	1
214	36	6	2025-04-12 17:00:00	2025-04-12 18:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Saturday 17:00	2025-04-04 22:36:53.48006+00	2025-04-04 22:37:27.819146+00	\N	1
215	36	6	2025-04-13 10:00:00	2025-04-13 11:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Sunday 10:00	2025-04-04 22:36:54.383119+00	2025-04-04 22:37:28.561867+00	\N	1
216	38	6	2025-04-13 10:00:00	2025-04-13 10:55:00	\N	f	\N	CANCELLED	0	Sesión de Pilates Mat - Sunday 10:00	2025-04-04 22:36:55.214244+00	2025-04-04 22:37:29.275659+00	\N	1
217	37	6	2025-04-13 12:00:00	2025-04-13 12:45:00	\N	f	\N	CANCELLED	0	Sesión de CrossFit Training - Sunday 12:00	2025-04-04 22:36:56.032677+00	2025-04-04 22:37:30.025985+00	\N	1
218	39	6	2025-04-13 12:00:00	2025-04-13 12:45:00	\N	f	\N	CANCELLED	0	Sesión de Spinning Power - Sunday 12:00	2025-04-04 22:36:57.109322+00	2025-04-04 22:37:30.656789+00	\N	1
219	40	6	2025-04-13 16:00:00	2025-04-13 17:00:00	\N	f	\N	CANCELLED	0	Sesión de Box Training - Sunday 16:00	2025-04-04 22:36:57.968854+00	2025-04-04 22:37:31.377894+00	\N	1
220	36	6	2025-04-13 16:00:00	2025-04-13 17:00:00	\N	f	\N	CANCELLED	0	Sesión de Yoga Flow - Sunday 16:00	2025-04-04 22:36:58.80084+00	2025-04-04 22:37:32.088592+00	\N	1
223	43	6	2025-04-07 10:00:00.517626	2025-04-07 11:00:00.517635	\N	f	\N	CANCELLED	0	Sesión creada automáticamente para pruebas de integración	2025-04-06 15:22:42.752214+00	2025-04-06 15:22:43.957109+00	\N	1
224	44	6	2025-04-07 10:00:00.060509	2025-04-07 11:00:00.060523	\N	f	\N	CANCELLED	0	Sesión creada automáticamente para pruebas de integración	2025-04-06 15:24:20.316578+00	2025-04-06 15:24:21.93628+00	\N	1
225	45	6	2025-04-07 10:00:00.380548	2025-04-07 11:00:00.380558	\N	f	\N	CANCELLED	0	Sesión creada automáticamente para pruebas de integración	2025-04-06 15:26:03.63564+00	2025-04-06 15:26:07.755483+00	\N	1
228	48	6	2025-04-07 10:00:00.418931	2025-04-07 11:00:00.418931	\N	f	\N	SCHEDULED	0	\N	2025-04-06 15:29:08.994276+00	\N	\N	1
229	48	6	2025-04-07 14:00:00.119291	2025-04-07 15:00:00.119291	\N	f	\N	SCHEDULED	0	\N	2025-04-06 15:29:10.37912+00	\N	\N	1
234	53	6	2025-04-07 18:30:00	2025-04-07 19:30:00	\N	f	\N	CANCELLED	0	Sesión de Monday	2025-04-06 15:31:09.663816+00	2025-04-06 15:32:13.253349+00	\N	1
231	51	6	2025-04-07 09:00:00	2025-04-07 09:55:00	\N	f	\N	CANCELLED	0	Sesión de Monday	2025-04-06 15:31:05.89891+00	2025-04-06 15:32:10.278518+00	\N	1
232	50	6	2025-04-07 13:00:00	2025-04-07 13:45:00	\N	f	\N	CANCELLED	0	Sesión de Monday	2025-04-06 15:31:07.153915+00	2025-04-06 15:32:11.233261+00	\N	1
235	49	6	2025-04-07 18:30:00	2025-04-07 19:30:00	\N	f	\N	CANCELLED	0	Sesión de Monday	2025-04-06 15:31:11.233762+00	2025-04-06 15:32:14.293235+00	\N	1
236	51	6	2025-04-08 08:30:00	2025-04-08 09:25:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-06 15:31:12.81386+00	2025-04-06 15:32:15.27334+00	\N	1
237	52	6	2025-04-08 08:30:00	2025-04-08 09:15:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-06 15:31:14.714172+00	2025-04-06 15:32:16.253243+00	\N	1
238	49	6	2025-04-08 14:00:00	2025-04-08 15:00:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-06 15:31:15.913739+00	2025-04-06 15:32:17.233385+00	\N	1
239	53	6	2025-04-08 14:00:00	2025-04-08 15:00:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-06 15:31:17.173716+00	2025-04-06 15:32:18.173183+00	\N	1
240	50	6	2025-04-08 19:00:00	2025-04-08 19:45:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-06 15:31:18.474221+00	2025-04-06 15:32:19.198369+00	\N	1
241	51	6	2025-04-08 19:00:00	2025-04-08 19:55:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-06 15:31:19.758722+00	2025-04-06 15:32:20.193304+00	\N	1
242	50	6	2025-04-09 09:00:00	2025-04-09 09:45:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-06 15:31:21.033826+00	2025-04-06 15:32:21.193328+00	\N	1
243	49	6	2025-04-09 09:00:00	2025-04-09 10:00:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-06 15:31:22.293912+00	2025-04-06 15:32:22.158341+00	\N	1
244	53	6	2025-04-09 13:00:00	2025-04-09 14:00:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-06 15:31:23.529309+00	2025-04-06 15:32:23.093246+00	\N	1
245	52	6	2025-04-09 13:00:00	2025-04-09 13:45:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-06 15:31:25.13369+00	2025-04-06 15:32:24.508273+00	\N	1
246	51	6	2025-04-09 18:30:00	2025-04-09 19:25:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-06 15:31:26.36375+00	2025-04-06 15:32:25.498269+00	\N	1
248	49	6	2025-04-10 08:30:00	2025-04-10 09:30:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-06 15:31:28.833761+00	2025-04-06 15:32:27.493322+00	\N	1
249	53	6	2025-04-10 08:30:00	2025-04-10 09:30:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-06 15:31:30.01378+00	2025-04-06 15:32:28.473098+00	\N	1
250	52	6	2025-04-10 14:00:00	2025-04-10 14:45:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-06 15:31:31.528665+00	2025-04-06 15:32:30.298401+00	\N	1
251	51	6	2025-04-10 14:00:00	2025-04-10 14:55:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-06 15:31:32.773641+00	2025-04-06 15:32:31.793273+00	\N	1
252	50	6	2025-04-10 19:00:00	2025-04-10 19:45:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-06 15:31:33.973776+00	2025-04-06 15:32:32.933313+00	\N	1
253	49	6	2025-04-10 19:00:00	2025-04-10 20:00:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-06 15:31:35.168637+00	2025-04-06 15:32:33.913277+00	\N	1
254	51	6	2025-04-11 09:00:00	2025-04-11 09:55:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-06 15:31:36.413731+00	2025-04-06 15:32:35.033274+00	\N	1
255	52	6	2025-04-11 09:00:00	2025-04-11 09:45:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-06 15:31:37.693722+00	2025-04-06 15:32:35.993251+00	\N	1
256	49	6	2025-04-11 13:00:00	2025-04-11 14:00:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-06 15:31:38.953655+00	2025-04-06 15:32:36.953227+00	\N	1
257	50	6	2025-04-11 13:00:00	2025-04-11 13:45:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-06 15:31:40.174132+00	2025-04-06 15:32:37.933065+00	\N	1
258	53	6	2025-04-11 18:30:00	2025-04-11 19:30:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-06 15:31:41.413697+00	2025-04-06 15:32:38.933146+00	\N	1
260	49	6	2025-04-12 10:00:00	2025-04-12 11:00:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-06 15:31:44.168728+00	2025-04-06 15:32:41.23813+00	\N	1
261	50	6	2025-04-12 10:00:00	2025-04-12 10:45:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-06 15:31:45.39863+00	2025-04-06 15:32:42.233154+00	\N	1
262	52	6	2025-04-12 12:00:00	2025-04-12 12:45:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-06 15:31:46.638599+00	2025-04-06 15:32:43.278225+00	\N	1
263	53	6	2025-04-12 12:00:00	2025-04-12 13:00:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-06 15:31:47.843606+00	2025-04-06 15:32:44.258158+00	\N	1
264	51	6	2025-04-12 17:00:00	2025-04-12 17:55:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-06 15:31:49.148521+00	2025-04-06 15:32:45.253271+00	\N	1
265	49	6	2025-04-12 17:00:00	2025-04-12 18:00:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-06 15:31:50.413707+00	2025-04-06 15:32:46.233247+00	\N	1
266	49	6	2025-04-13 10:00:00	2025-04-13 11:00:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-06 15:31:51.648957+00	2025-04-06 15:32:47.218146+00	\N	1
230	49	6	2025-04-07 09:00:00	2025-04-07 10:00:00	\N	f	\N	CANCELLED	0	Sesión de Monday	2025-04-06 15:31:04.693841+00	2025-04-06 15:32:03.70353+00	\N	1
233	52	6	2025-04-07 13:00:00	2025-04-07 13:45:00	\N	f	\N	CANCELLED	0	¡Clase especial! Traer equipo adicional.	2025-04-06 15:31:08.393803+00	2025-04-06 15:32:12.253411+00	\N	1
247	50	6	2025-04-09 18:30:00	2025-04-09 19:15:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-06 15:31:27.613772+00	2025-04-06 15:32:26.463201+00	\N	1
259	51	6	2025-04-11 18:30:00	2025-04-11 19:25:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-06 15:31:42.973625+00	2025-04-06 15:32:39.913093+00	\N	1
267	51	6	2025-04-13 10:00:00	2025-04-13 10:55:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-06 15:31:53.533538+00	2025-04-06 15:32:48.203125+00	\N	1
268	50	6	2025-04-13 12:00:00	2025-04-13 12:45:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-06 15:31:54.853654+00	2025-04-06 15:32:49.238593+00	\N	1
269	52	6	2025-04-13 12:00:00	2025-04-13 12:45:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-06 15:31:56.758628+00	2025-04-06 15:32:50.218197+00	\N	1
270	53	6	2025-04-13 16:00:00	2025-04-13 17:00:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-06 15:31:57.974025+00	2025-04-06 15:32:51.193042+00	\N	1
271	49	6	2025-04-13 16:00:00	2025-04-13 17:00:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-06 15:31:59.539046+00	2025-04-06 15:32:52.238115+00	\N	1
272	54	6	2025-04-09 10:00:00.802511	2025-04-09 11:00:00.802531	\N	f	\N	CANCELLED	0	Sesión creada automáticamente para pruebas de integración	2025-04-08 04:55:30.925569+00	2025-04-08 04:55:31.805943+00	\N	1
273	55	6	2025-04-14 09:00:00	2025-04-14 10:00:00	\N	f	\N	CANCELLED	0	Sesión de Monday	2025-04-08 04:56:23.878566+00	2025-04-08 04:57:06.085767+00	\N	1
284	57	6	2025-04-15 19:00:00	2025-04-15 19:55:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-08 04:56:33.883314+00	2025-04-08 04:57:17.036812+00	\N	1
274	57	6	2025-04-14 09:00:00	2025-04-14 09:55:00	\N	f	\N	CANCELLED	0	Sesión de Monday	2025-04-08 04:56:24.836155+00	2025-04-08 04:57:09.899008+00	\N	1
275	56	6	2025-04-14 13:00:00	2025-04-14 13:45:00	\N	f	\N	CANCELLED	0	Sesión de Monday	2025-04-08 04:56:25.629122+00	2025-04-08 04:57:10.531176+00	\N	1
276	58	6	2025-04-14 13:00:00	2025-04-14 13:45:00	\N	f	\N	CANCELLED	0	¡Clase especial! Traer equipo adicional.	2025-04-08 04:56:26.466484+00	2025-04-08 04:57:11.24485+00	\N	1
277	59	6	2025-04-14 18:30:00	2025-04-14 19:30:00	\N	f	\N	CANCELLED	0	Sesión de Monday	2025-04-08 04:56:27.393985+00	2025-04-08 04:57:11.928741+00	\N	1
278	55	6	2025-04-14 18:30:00	2025-04-14 19:30:00	\N	f	\N	CANCELLED	0	Sesión de Monday	2025-04-08 04:56:28.297961+00	2025-04-08 04:57:12.782289+00	\N	1
279	57	6	2025-04-15 08:30:00	2025-04-15 09:25:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-08 04:56:29.150562+00	2025-04-08 04:57:13.471307+00	\N	1
280	58	6	2025-04-15 08:30:00	2025-04-15 09:15:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-08 04:56:30.124052+00	2025-04-08 04:57:14.139383+00	\N	1
281	55	6	2025-04-15 14:00:00	2025-04-15 15:00:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-08 04:56:31.092142+00	2025-04-08 04:57:14.865074+00	\N	1
282	59	6	2025-04-15 14:00:00	2025-04-15 15:00:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-08 04:56:31.974913+00	2025-04-08 04:57:15.593091+00	\N	1
283	56	6	2025-04-15 19:00:00	2025-04-15 19:45:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-08 04:56:32.892216+00	2025-04-08 04:57:16.334892+00	\N	1
285	56	6	2025-04-16 09:00:00	2025-04-16 09:45:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-08 04:56:34.790721+00	2025-04-08 04:57:17.746221+00	\N	1
286	55	6	2025-04-16 09:00:00	2025-04-16 10:00:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-08 04:56:35.723766+00	2025-04-08 04:57:18.379712+00	\N	1
287	59	6	2025-04-16 13:00:00	2025-04-16 14:00:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-08 04:56:36.617674+00	2025-04-08 04:57:19.171981+00	\N	1
288	58	6	2025-04-16 13:00:00	2025-04-16 13:45:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-08 04:56:37.457839+00	2025-04-08 04:57:19.849183+00	\N	1
289	57	6	2025-04-16 18:30:00	2025-04-16 19:25:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-08 04:56:38.276223+00	2025-04-08 04:57:20.551029+00	\N	1
290	56	6	2025-04-16 18:30:00	2025-04-16 19:15:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-08 04:56:39.323816+00	2025-04-08 04:57:21.360248+00	\N	1
291	55	6	2025-04-17 08:30:00	2025-04-17 09:30:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-08 04:56:40.267145+00	2025-04-08 04:57:22.213888+00	\N	1
292	59	6	2025-04-17 08:30:00	2025-04-17 09:30:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-08 04:56:41.154992+00	2025-04-08 04:57:22.858813+00	\N	1
293	58	6	2025-04-17 14:00:00	2025-04-17 14:45:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-08 04:56:42.125323+00	2025-04-08 04:57:23.537315+00	\N	1
294	57	6	2025-04-17 14:00:00	2025-04-17 14:55:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-08 04:56:43.078553+00	2025-04-08 04:57:24.173186+00	\N	1
295	56	6	2025-04-17 19:00:00	2025-04-17 19:45:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-08 04:56:43.92531+00	2025-04-08 04:57:25.179622+00	\N	1
296	55	6	2025-04-17 19:00:00	2025-04-17 20:00:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-08 04:56:44.823196+00	2025-04-08 04:57:25.836292+00	\N	1
297	57	6	2025-04-18 09:00:00	2025-04-18 09:55:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-08 04:56:45.806275+00	2025-04-08 04:57:26.487929+00	\N	1
298	58	6	2025-04-18 09:00:00	2025-04-18 09:45:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-08 04:56:46.601368+00	2025-04-08 04:57:27.177674+00	\N	1
299	55	6	2025-04-18 13:00:00	2025-04-18 14:00:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-08 04:56:47.487928+00	2025-04-08 04:57:27.973172+00	\N	1
300	56	6	2025-04-18 13:00:00	2025-04-18 13:45:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-08 04:56:51.613346+00	2025-04-08 04:57:28.605879+00	\N	1
301	59	6	2025-04-18 18:30:00	2025-04-18 19:30:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-08 04:56:52.93516+00	2025-04-08 04:57:29.289717+00	\N	1
302	57	6	2025-04-18 18:30:00	2025-04-18 19:25:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-08 04:56:53.805892+00	2025-04-08 04:57:29.973439+00	\N	1
303	55	6	2025-04-19 10:00:00	2025-04-19 11:00:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-08 04:56:54.81843+00	2025-04-08 04:57:30.726116+00	\N	1
304	56	6	2025-04-19 10:00:00	2025-04-19 10:45:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-08 04:56:55.609604+00	2025-04-08 04:57:31.351484+00	\N	1
305	58	6	2025-04-19 12:00:00	2025-04-19 12:45:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-08 04:56:56.523999+00	2025-04-08 04:57:32.051958+00	\N	1
306	59	6	2025-04-19 12:00:00	2025-04-19 13:00:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-08 04:56:57.350603+00	2025-04-08 04:57:33.610828+00	\N	1
315	60	6	2025-04-09 10:00:00.378933	2025-04-09 11:00:00.378933	\N	f	\N	SCHEDULED	0	\N	2025-04-08 04:57:34.245301+00	\N	\N	1
307	57	6	2025-04-19 17:00:00	2025-04-19 17:55:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-08 04:56:58.310499+00	2025-04-08 04:57:35.083974+00	\N	1
316	60	6	2025-04-09 14:00:00.956604	2025-04-09 15:00:00.956604	\N	f	\N	SCHEDULED	0	\N	2025-04-08 04:57:35.752105+00	\N	\N	1
308	55	6	2025-04-19 17:00:00	2025-04-19 18:00:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-08 04:56:59.191175+00	2025-04-08 04:57:36.549502+00	\N	1
309	55	6	2025-04-20 10:00:00	2025-04-20 11:00:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-08 04:57:00.117202+00	2025-04-08 04:57:37.952416+00	\N	1
310	57	6	2025-04-20 10:00:00	2025-04-20 10:55:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-08 04:57:01.094184+00	2025-04-08 04:57:38.635995+00	\N	1
311	56	6	2025-04-20 12:00:00	2025-04-20 12:45:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-08 04:57:01.879058+00	2025-04-08 04:57:39.33411+00	\N	1
312	58	6	2025-04-20 12:00:00	2025-04-20 12:45:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-08 04:57:02.734758+00	2025-04-08 04:57:40.137473+00	\N	1
313	59	6	2025-04-20 16:00:00	2025-04-20 17:00:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-08 04:57:03.593787+00	2025-04-08 04:57:40.829525+00	\N	1
314	55	6	2025-04-20 16:00:00	2025-04-20 17:00:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-08 04:57:04.397909+00	2025-04-08 04:57:41.523811+00	\N	1
363	2	6	2025-04-09 10:00:00	2025-04-09 11:00:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-09 07:01:40.328067+00	2025-04-09 07:01:42.202599+00	\N	1
364	2	6	2025-04-09 10:00:00	2025-04-09 11:00:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-09 07:01:59.112852+00	2025-04-09 07:02:00.303678+00	\N	1
365	98	6	2025-04-10 10:00:00.129879	2025-04-10 11:00:00.129888	\N	f	\N	CANCELLED	0	Sesión creada automáticamente para pruebas de integración	2025-04-09 07:03:14.271705+00	2025-04-09 07:03:15.447079+00	\N	1
367	103	6	2025-04-14 09:00:00	2025-04-14 09:55:00	\N	f	\N	CANCELLED	0	Sesión de Monday	2025-04-09 07:05:47.316982+00	2025-04-09 07:06:45.838205+00	\N	1
368	102	6	2025-04-14 13:00:00	2025-04-14 13:45:00	\N	f	\N	CANCELLED	0	Sesión de Monday	2025-04-09 07:05:48.523665+00	2025-04-09 07:06:46.937194+00	\N	1
370	105	6	2025-04-14 18:30:00	2025-04-14 19:30:00	\N	f	\N	CANCELLED	0	Sesión de Monday	2025-04-09 07:05:51.088224+00	2025-04-09 07:06:49.064721+00	\N	1
371	101	6	2025-04-14 18:30:00	2025-04-14 19:30:00	\N	f	\N	CANCELLED	0	Sesión de Monday	2025-04-09 07:05:52.378836+00	2025-04-09 07:06:50.195199+00	\N	1
366	101	6	2025-04-14 09:00:00	2025-04-14 10:00:00	\N	f	\N	CANCELLED	0	Sesión de Monday	2025-04-09 07:05:46.018234+00	2025-04-09 07:06:40.172571+00	\N	1
369	104	6	2025-04-14 13:00:00	2025-04-14 13:45:00	\N	f	\N	CANCELLED	0	¡Clase especial! Traer equipo adicional.	2025-04-09 07:05:49.818695+00	2025-04-09 07:06:47.990481+00	\N	1
372	103	6	2025-04-15 08:30:00	2025-04-15 09:25:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-09 07:05:53.662597+00	2025-04-09 07:06:51.190881+00	\N	1
373	104	6	2025-04-15 08:30:00	2025-04-15 09:15:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-09 07:05:54.842264+00	2025-04-09 07:06:52.296819+00	\N	1
374	101	6	2025-04-15 14:00:00	2025-04-15 15:00:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-09 07:05:56.155267+00	2025-04-09 07:06:53.446511+00	\N	1
375	105	6	2025-04-15 14:00:00	2025-04-15 15:00:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-09 07:05:57.373223+00	2025-04-09 07:06:54.475904+00	\N	1
376	102	6	2025-04-15 19:00:00	2025-04-15 19:45:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-09 07:05:58.582146+00	2025-04-09 07:06:55.684866+00	\N	1
377	103	6	2025-04-15 19:00:00	2025-04-15 19:55:00	\N	f	\N	CANCELLED	0	Sesión de Tuesday	2025-04-09 07:05:59.878676+00	2025-04-09 07:06:56.842294+00	\N	1
378	102	6	2025-04-16 09:00:00	2025-04-16 09:45:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-09 07:06:01.147451+00	2025-04-09 07:06:57.862735+00	\N	1
379	101	6	2025-04-16 09:00:00	2025-04-16 10:00:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-09 07:06:02.52105+00	2025-04-09 07:06:58.986337+00	\N	1
380	105	6	2025-04-16 13:00:00	2025-04-16 14:00:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-09 07:06:03.694184+00	2025-04-09 07:07:00.185846+00	\N	1
381	104	6	2025-04-16 13:00:00	2025-04-16 13:45:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-09 07:06:04.858908+00	2025-04-09 07:07:01.314436+00	\N	1
382	103	6	2025-04-16 18:30:00	2025-04-16 19:25:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-09 07:06:06.098596+00	2025-04-09 07:07:02.341887+00	\N	1
383	102	6	2025-04-16 18:30:00	2025-04-16 19:15:00	\N	f	\N	CANCELLED	0	Sesión de Wednesday	2025-04-09 07:06:07.345643+00	2025-04-09 07:07:03.345836+00	\N	1
384	101	6	2025-04-17 08:30:00	2025-04-17 09:30:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-09 07:06:08.651114+00	2025-04-09 07:07:04.36611+00	\N	1
385	105	6	2025-04-17 08:30:00	2025-04-17 09:30:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-09 07:06:09.824889+00	2025-04-09 07:07:05.536963+00	\N	1
386	104	6	2025-04-17 14:00:00	2025-04-17 14:45:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-09 07:06:11.147688+00	2025-04-09 07:07:06.55681+00	\N	1
387	103	6	2025-04-17 14:00:00	2025-04-17 14:55:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-09 07:06:12.337268+00	2025-04-09 07:07:07.67879+00	\N	1
388	102	6	2025-04-17 19:00:00	2025-04-17 19:45:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-09 07:06:13.615037+00	2025-04-09 07:07:08.74576+00	\N	1
389	101	6	2025-04-17 19:00:00	2025-04-17 20:00:00	\N	f	\N	CANCELLED	0	Sesión de Thursday	2025-04-09 07:06:14.867269+00	2025-04-09 07:07:09.763896+00	\N	1
390	103	6	2025-04-18 09:00:00	2025-04-18 09:55:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-09 07:06:16.027294+00	2025-04-09 07:07:10.90774+00	\N	1
391	104	6	2025-04-18 09:00:00	2025-04-18 09:45:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-09 07:06:17.406428+00	2025-04-09 07:07:11.970003+00	\N	1
392	101	6	2025-04-18 13:00:00	2025-04-18 14:00:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-09 07:06:18.610903+00	2025-04-09 07:07:12.974895+00	\N	1
393	102	6	2025-04-18 13:00:00	2025-04-18 13:45:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-09 07:06:19.88353+00	2025-04-09 07:07:14.267585+00	\N	1
394	105	6	2025-04-18 18:30:00	2025-04-18 19:30:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-09 07:06:21.096907+00	2025-04-09 07:07:15.255789+00	\N	1
395	103	6	2025-04-18 18:30:00	2025-04-18 19:25:00	\N	f	\N	CANCELLED	0	Sesión de Friday	2025-04-09 07:06:22.391308+00	2025-04-09 07:07:16.408689+00	\N	1
396	101	6	2025-04-19 10:00:00	2025-04-19 11:00:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-09 07:06:23.665365+00	2025-04-09 07:07:17.500951+00	\N	1
397	102	6	2025-04-19 10:00:00	2025-04-19 10:45:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-09 07:06:24.865254+00	2025-04-09 07:07:18.511799+00	\N	1
398	104	6	2025-04-19 12:00:00	2025-04-19 12:45:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-09 07:06:26.182753+00	2025-04-09 07:07:19.835411+00	\N	1
399	105	6	2025-04-19 12:00:00	2025-04-19 13:00:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-09 07:06:27.368484+00	2025-04-09 07:07:20.956524+00	\N	1
400	103	6	2025-04-19 17:00:00	2025-04-19 17:55:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-09 07:06:28.658303+00	2025-04-09 07:07:22.002942+00	\N	1
401	101	6	2025-04-19 17:00:00	2025-04-19 18:00:00	\N	f	\N	CANCELLED	0	Sesión de Saturday	2025-04-09 07:06:29.867218+00	2025-04-09 07:07:23.135113+00	\N	1
402	101	6	2025-04-20 10:00:00	2025-04-20 11:00:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-09 07:06:31.132226+00	2025-04-09 07:07:24.15697+00	\N	1
403	103	6	2025-04-20 10:00:00	2025-04-20 10:55:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-09 07:06:32.440045+00	2025-04-09 07:07:25.202815+00	\N	1
404	102	6	2025-04-20 12:00:00	2025-04-20 12:45:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-09 07:06:33.641503+00	2025-04-09 07:07:26.29677+00	\N	1
405	104	6	2025-04-20 12:00:00	2025-04-20 12:45:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-09 07:06:35.024002+00	2025-04-09 07:07:27.289373+00	\N	1
406	105	6	2025-04-20 16:00:00	2025-04-20 17:00:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-09 07:06:36.249376+00	2025-04-09 07:07:28.327818+00	\N	1
407	101	6	2025-04-20 16:00:00	2025-04-20 17:00:00	\N	f	\N	CANCELLED	0	Sesión de Sunday	2025-04-09 07:06:37.58631+00	2025-04-09 07:07:29.410237+00	\N	1
\.


--
-- Data for Name: device_tokens; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.device_tokens (id, user_id, device_token, platform, is_active, last_used, created_at, updated_at) FROM stdin;
f4e417ed-a7ec-499a-b122-1bf22f0a1d01	auth0|67d5d64d64ccf1c522a6950b	test-token-android-123	android	t	\N	2025-04-08 15:20:53.738862+00	2025-04-08 11:22:35.610936+00
\.


--
-- Data for Name: event_participations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.event_participations (id, event_id, member_id, status, attended, registered_at, updated_at, gym_id) FROM stdin;
1	1	5	REGISTERED	f	2025-03-25 04:41:16.68269	2025-03-25 04:41:16.682694	1
7	2	4	REGISTERED	f	2025-04-01 05:17:02.080813	2025-04-01 05:17:02.080813	1
9	1	4	REGISTERED	f	2025-04-01 05:17:19.897729	2025-04-01 05:17:19.897729	1
10	3	4	REGISTERED	f	2025-04-01 05:20:43.551138	2025-04-01 05:20:43.551138	1
11	7	4	REGISTERED	f	2025-04-02 01:07:09.82328	2025-04-02 01:07:09.82328	1
39	51	4	REGISTERED	f	2025-04-11 05:10:58.492758	2025-04-11 05:10:58.492758	2
\.


--
-- Data for Name: events; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.events (id, title, description, start_time, end_time, location, max_participants, status, creator_id, created_at, updated_at, gym_id) FROM stdin;
46	Carrera Parque Cespedes	Maraton Salida Parque Cespedes	2025-04-11 02:39:52.298	2025-04-11 02:39:52.298	Parque Cespedes	50	COMPLETED	4	2025-04-11 02:40:48.677907	2025-04-11 03:00:01.001619	1
51	Runner	Runner	2025-04-12 05:09:01.125	2025-04-12 05:09:01.125	Puente Miami Beach	60	COMPLETED	4	2025-04-11 05:10:14.033072	2025-04-12 09:00:01.359941	2
8	Evento de Prueba 1743733329	Este es un evento creado automáticamente para pruebas de integración	2025-04-04 10:00:00.237699	2025-04-04 12:00:00.237707	Sala de Pruebas	15	COMPLETED	4	2025-04-04 02:22:09.579498	2025-04-09 07:15:05.815437	1
2	Runner Downtown	Carrera en el downtown	2025-04-01 03:09:38.253	2025-04-01 03:09:38.253	Downtown Miami	20	COMPLETED	4	2025-04-01 03:17:45.892683	2025-04-09 07:15:01.97136	1
3	Runner Downtown	Carrera Bayside	2025-04-01 03:09:38.253	2025-04-01 03:09:38.253	Downtown Miami	20	COMPLETED	4	2025-04-01 03:22:29.850997	2025-04-09 07:15:02.851463	1
6	Recogida de basura playa	Recogida de basura en la playa de Miami Beach	2025-04-02 20:03:49.48	2025-04-02 22:03:49.48	Miai Beach	100	COMPLETED	4	2025-04-01 20:24:03.796648	2025-04-09 07:15:03.517371	1
7	Recogida de basura playa	Recogida de basura en la playa	2025-04-02 20:03:49.48	2025-04-02 22:03:49.48	Hialeah	100	COMPLETED	4	2025-04-01 20:27:47.382393	2025-04-09 07:15:04.247439	1
1	Carrera Runner	Carrera Venetian	2025-03-16 21:07:43.275	2025-03-16 21:07:43.275	Venetian	20	COMPLETED	4	2025-03-16 21:08:27.418508	2025-04-09 07:15:05.074992	1
9	Evento de Prueba 1743733393	Este es un evento creado automáticamente para pruebas de integración	2025-04-04 10:00:00.61722	2025-04-04 12:00:00.617241	Sala de Pruebas	15	COMPLETED	4	2025-04-04 02:23:13.954416	2025-04-09 07:15:06.393968	1
10	Evento de Prueba 1743733507	Este es un evento creado automáticamente para pruebas de integración	2025-04-04 10:00:00.020446	2025-04-04 12:00:00.020461	Sala de Pruebas	15	COMPLETED	4	2025-04-04 02:25:08.742143	2025-04-09 07:15:07.013582	1
11	Evento de Prueba 1743733524	Este es un evento creado automáticamente para pruebas de integración	2025-04-04 10:00:00.908783	2025-04-04 12:00:00.908793	Sala de Pruebas	15	COMPLETED	4	2025-04-04 02:25:25.287039	2025-04-09 07:15:07.827038	1
12	Evento de Prueba 1743733583	Este es un evento creado automáticamente para pruebas de integración	2025-04-04 10:00:00.595565	2025-04-04 12:00:00.595575	Sala de Pruebas	15	COMPLETED	4	2025-04-04 02:26:25.425715	2025-04-09 07:15:08.699992	1
45	Evento de prueba automatización	Este evento se completará automáticamente en 5 minutos	2025-04-09 03:18:24.623817	2025-04-09 03:23:24.623817	Sala de pruebas	10	COMPLETED	4	2025-04-09 07:20:57.788254	2025-04-09 07:23:25.074833	1
44	Test Event 20250409011905	Evento creado automáticamente para pruebas	2025-04-10 10:00:00	2025-04-10 12:00:00	Sala de pruebas	12	COMPLETED	6	2025-04-09 05:19:05.973136	2025-04-10 16:00:01.237511	1
\.


--
-- Data for Name: gym_hours; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.gym_hours (id, day_of_week, open_time, close_time, is_closed, created_at, updated_at, gym_id) FROM stdin;
1	0	09:00:00	21:00:00	f	2025-04-03 02:14:49.07651+00	\N	1
2	1	09:00:00	21:00:00	f	2025-04-03 02:14:49.495446+00	\N	1
3	2	09:00:00	21:00:00	f	2025-04-03 02:14:49.959409+00	\N	1
4	3	09:00:00	21:00:00	f	2025-04-03 02:14:50.474219+00	\N	1
5	4	09:00:00	21:00:00	f	2025-04-03 02:14:50.967795+00	\N	1
6	5	09:00:00	21:00:00	f	2025-04-03 02:14:51.622566+00	\N	1
7	6	09:00:00	21:00:00	t	2025-04-03 02:14:52.103478+00	\N	1
9	0	09:00:00	21:00:00	f	2025-04-11 05:16:25.195651+00	\N	2
10	1	09:00:00	21:00:00	f	2025-04-11 05:16:25.98711+00	\N	2
11	2	09:00:00	21:00:00	f	2025-04-11 05:16:26.490698+00	\N	2
12	3	09:00:00	21:00:00	f	2025-04-11 05:16:26.994156+00	\N	2
13	4	09:00:00	21:00:00	f	2025-04-11 05:16:27.478891+00	\N	2
14	5	10:00:00	18:00:00	f	2025-04-11 05:16:28.068413+00	\N	2
16	6	\N	\N	t	2025-04-11 05:18:51.544922+00	\N	2
\.


--
-- Data for Name: gym_special_hours; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.gym_special_hours (id, date, open_time, close_time, is_closed, description, created_at, updated_at, created_by, gym_id) FROM stdin;
1	2025-04-12	10:00:00	18:00:00	f	Aplicado desde plantilla (5)	2025-04-11 06:14:07.992649+00	\N	\N	2
2	2025-04-13	\N	\N	t	Aplicado desde plantilla (6)	2025-04-11 06:14:07.992649+00	\N	\N	2
3	2025-04-14	09:00:00	21:00:00	f	Aplicado desde plantilla (0)	2025-04-11 06:14:07.992649+00	\N	\N	2
4	2025-04-15	09:00:00	21:00:00	f	Aplicado desde plantilla (1)	2025-04-11 06:14:07.992649+00	\N	\N	2
5	2025-04-16	09:00:00	21:00:00	f	Aplicado desde plantilla (2)	2025-04-11 06:14:07.992649+00	\N	\N	2
6	2025-04-17	09:00:00	21:00:00	f	Aplicado desde plantilla (3)	2025-04-11 06:14:07.992649+00	\N	\N	2
8	2025-04-19	10:00:00	18:00:00	f	Aplicado desde plantilla (5)	2025-04-11 06:14:07.992649+00	\N	\N	2
9	2025-04-20	\N	\N	t	Aplicado desde plantilla (6)	2025-04-11 06:14:07.992649+00	\N	\N	2
10	2025-04-21	09:00:00	21:00:00	f	Aplicado desde plantilla (0)	2025-04-11 06:14:07.992649+00	\N	\N	2
11	2025-04-22	09:00:00	21:00:00	f	Aplicado desde plantilla (1)	2025-04-11 06:14:07.992649+00	\N	\N	2
12	2025-04-23	09:00:00	21:00:00	f	Aplicado desde plantilla (2)	2025-04-11 06:14:07.992649+00	\N	\N	2
13	2025-04-24	09:00:00	21:00:00	f	Aplicado desde plantilla (3)	2025-04-11 06:14:07.992649+00	\N	\N	2
14	2025-04-25	09:00:00	21:00:00	f	Aplicado desde plantilla (4)	2025-04-11 06:14:07.992649+00	\N	\N	2
7	2025-04-18	06:00:00	16:00:00	f		2025-04-11 06:14:07.992649+00	2025-04-11 06:31:42.801752+00	\N	2
\.


--
-- Data for Name: gyms; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.gyms (id, name, subdomain, logo_url, address, phone, email, description, is_active, created_at, updated_at) FROM stdin;
1	Gimnasio Predeterminado	default	\N	\N	\N	\N	\N	t	2025-04-01 02:36:24.159799	2025-04-01 02:36:24.159799
2	CKO-Downtown	iguqsom-q0l3c9074jqr57l5qp-8ne-0t73jtit8	https://example.com/	string	string	user@example.com	string	t	2025-04-08 21:32:23.516932	2025-04-08 21:32:23.516935
\.


--
-- Data for Name: trainermemberrelationship; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.trainermemberrelationship (id, trainer_id, member_id, status, created_at, updated_at, start_date, end_date, notes, created_by) FROM stdin;
\.


--
-- Data for Name: user; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public."user" (id, email, is_active, is_superuser, created_at, updated_at, auth0_id, picture, locale, auth0_metadata, role, phone_number, birth_date, height, weight, bio, goals, health_conditions, first_name, last_name) FROM stdin;
5	alexmon@gmail.com	t	f	2025-03-25 02:30:48.670507+00	\N	auth0|67e215563eeee752d79c2c38		\N	{"sub": "auth0|67e215563eeee752d79c2c38", "email": "alexmon@gmail.com", "name": "", "nickname": "", "picture": "", "email_verified": false, "created_at": "2025-03-25T02:30:46.629Z", "auth0_metadata": {"email": "alexmon@gmail.com", "tenant": "dev-gd5crfe6qbqlu23p", "user_id": "auth0|67e215563eeee752d79c2c38", "app_metadata": {}, "user_metadata": {}, "email_verified": false, "phone_verified": false}}	MEMBER	\N	\N	\N	\N	\N	\N	\N		
7	josedaniel@gmail.com	t	f	2025-04-10 01:12:50.537055+00	\N	auth0|67f71b1172cf9889b9ec757c		\N	{"sub": "auth0|67f71b1172cf9889b9ec757c", "email": "josedaniel@gmail.com", "name": "", "nickname": "", "picture": "", "email_verified": false, "created_at": "2025-04-10T01:12:49.985Z", "auth0_metadata": {"email": "josedaniel@gmail.com", "tenant": "dev-gd5crfe6qbqlu23p", "user_id": "auth0|67f71b1172cf9889b9ec757c", "app_metadata": {}, "user_metadata": {}, "email_verified": false, "phone_verified": false}}	MEMBER	\N	\N	\N	\N	\N	\N	\N		
4	alexmontesino96@icloud.com	t	t	2025-03-16 17:53:48.108111+00	2025-04-10 21:32:34.541567+00	auth0|67d5d64d64ccf1c522a6950b	https://ueijlkythlkqadxymzqd.supabase.co/storage/v1/object/public/userphotoprofile/auth0_67d5d64d64ccf1c522a6950b_df0d375618ad4f6896dd28ece0c5021f.jpeg?	\N	{"sub": "auth0|67d5d64d64ccf1c522a6950b", "email": "admin_auth0_67d5d64d64ccf1c522a6950b@example.com", "name": null, "picture": null}	SUPER_ADMIN	\N	\N	\N	190	\N	\N	\N	Alex	Montesino
2	josepaul@gmail.com	t	f	2025-03-16 00:05:07.465159+00	2025-04-10 21:46:58.03602+00	auth0|67d615b1a9ea8e1393906d4d		\N	{"sub": "auth0|67d615b1a9ea8e1393906d4d", "email": "josepaul@gmail.com", "name": "", "nickname": "", "picture": "", "email_verified": false, "created_at": "2025-03-16T00:05:05.527Z", "auth0_metadata": {"email": "josepaul@gmail.com", "tenant": "dev-gd5crfe6qbqlu23p", "user_id": "auth0|67d615b1a9ea8e1393906d4d", "app_metadata": {}, "user_metadata": {}, "email_verified": false, "phone_verified": false}}	TRAINER	\N	\N	\N	\N	\N	\N	\N		
6	alextrainer@gmail.com	t	f	2025-04-04 05:12:29.774772+00	2025-04-12 19:36:05.47061+00	auth0|67ef66dfcb9e2a66485f2dde	https://ueijlkythlkqadxymzqd.supabase.co/storage/v1/object/public/userphotoprofile/auth0_67ef66dfcb9e2a66485f2dde_e7e7d67372fb40148f13b1df8c6d5284.png?	\N	{"sub": "auth0|67ef66dfcb9e2a66485f2dde", "email": "alextrainer@gmail.com"}	TRAINER	\N	\N	5.9	190	\N	\N	\N	Alex	Trainner
8	josepaul12@gmail.com	t	f	2025-04-10 01:26:09.417898+00	2025-04-13 06:12:26.785877+00	auth0|67f71e304b8a05024c163e04	https://ueijlkythlkqadxymzqd.supabase.co/storage/v1/object/public/userphotoprofile/auth0_67f71e304b8a05024c163e04_71e37e93cd5c4ae7b4ec9d25a3768833.png?	\N	{"sub": "auth0|67f71e304b8a05024c163e04", "email": "josepaul12@gmail.com", "name": "", "nickname": "", "picture": "", "email_verified": false, "created_at": "2025-04-10T01:26:08.937Z", "auth0_metadata": {"email": "josepaul12@gmail.com", "tenant": "dev-gd5crfe6qbqlu23p", "user_id": "auth0|67f71e304b8a05024c163e04", "username": "josepaul12", "app_metadata": {}, "user_metadata": {}, "email_verified": false, "phone_verified": false}}	MEMBER	\N	\N	5.9	180	\N	\N	\N	Jose Paul	Rodriguez
\.


--
-- Data for Name: user_gyms; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.user_gyms (id, user_id, gym_id, role, created_at) FROM stdin;
1	2	1	MEMBER	2025-03-16 00:05:07.465159
2	4	1	ADMIN	2025-03-16 17:53:48.108111
4	6	1	TRAINER	\N
5	8	1	MEMBER	2025-04-13 06:24:59.452909
3	5	1	TRAINER	2025-03-25 02:30:48.670507
\.


--
-- Data for Name: schema_migrations; Type: TABLE DATA; Schema: realtime; Owner: -
--

COPY realtime.schema_migrations (version, inserted_at) FROM stdin;
20211116024918	2025-03-14 22:50:53
20211116045059	2025-03-14 22:50:54
20211116050929	2025-03-14 22:50:54
20211116051442	2025-03-14 22:50:55
20211116212300	2025-03-14 22:50:56
20211116213355	2025-03-14 22:50:57
20211116213934	2025-03-14 22:50:57
20211116214523	2025-03-14 22:50:58
20211122062447	2025-03-14 22:50:59
20211124070109	2025-03-14 22:50:59
20211202204204	2025-03-14 22:51:00
20211202204605	2025-03-14 22:51:01
20211210212804	2025-03-14 22:51:03
20211228014915	2025-03-14 22:51:03
20220107221237	2025-03-14 22:51:04
20220228202821	2025-03-14 22:51:05
20220312004840	2025-03-14 22:51:05
20220603231003	2025-03-14 22:51:06
20220603232444	2025-03-14 22:51:07
20220615214548	2025-03-14 22:51:08
20220712093339	2025-03-14 22:51:08
20220908172859	2025-03-14 22:51:09
20220916233421	2025-03-14 22:51:10
20230119133233	2025-03-14 22:51:10
20230128025114	2025-03-14 22:51:11
20230128025212	2025-03-14 22:51:12
20230227211149	2025-03-14 22:51:12
20230228184745	2025-03-14 22:51:13
20230308225145	2025-03-14 22:51:14
20230328144023	2025-03-14 22:51:15
20231018144023	2025-03-14 22:51:15
20231204144023	2025-03-14 22:51:16
20231204144024	2025-03-14 22:51:17
20231204144025	2025-03-14 22:51:18
20240108234812	2025-03-14 22:51:19
20240109165339	2025-03-14 22:51:19
20240227174441	2025-03-14 22:51:21
20240311171622	2025-03-14 22:51:21
20240321100241	2025-03-14 22:51:23
20240401105812	2025-03-14 22:51:25
20240418121054	2025-03-14 22:51:26
20240523004032	2025-03-14 22:51:28
20240618124746	2025-03-14 22:51:29
20240801235015	2025-03-14 22:51:29
20240805133720	2025-03-14 22:51:30
20240827160934	2025-03-14 22:51:31
20240919163303	2025-03-14 22:51:32
20240919163305	2025-03-14 22:51:33
20241019105805	2025-03-14 22:51:33
20241030150047	2025-03-14 22:51:36
20241108114728	2025-03-14 22:51:37
20241121104152	2025-03-14 22:51:37
20241130184212	2025-03-14 22:51:38
20241220035512	2025-03-14 22:51:39
20241220123912	2025-03-14 22:51:40
20241224161212	2025-03-14 22:51:40
20250107150512	2025-03-14 22:51:41
20250110162412	2025-03-14 22:51:42
20250123174212	2025-03-14 22:51:42
20250128220012	2025-03-14 22:51:43
\.


--
-- Data for Name: subscription; Type: TABLE DATA; Schema: realtime; Owner: -
--

COPY realtime.subscription (id, subscription_id, entity, filters, claims, created_at) FROM stdin;
\.


--
-- Data for Name: buckets; Type: TABLE DATA; Schema: storage; Owner: -
--

COPY storage.buckets (id, name, owner, created_at, updated_at, public, avif_autodetection, file_size_limit, allowed_mime_types, owner_id) FROM stdin;
userphotoprofile	userphotoprofile	\N	2025-04-09 19:19:23.669597+00	2025-04-09 19:19:23.669597+00	f	f	\N	\N	\N
\.


--
-- Data for Name: migrations; Type: TABLE DATA; Schema: storage; Owner: -
--

COPY storage.migrations (id, name, hash, executed_at) FROM stdin;
0	create-migrations-table	e18db593bcde2aca2a408c4d1100f6abba2195df	2025-03-14 22:45:29.918932
1	initialmigration	6ab16121fbaa08bbd11b712d05f358f9b555d777	2025-03-14 22:45:29.927611
2	storage-schema	5c7968fd083fcea04050c1b7f6253c9771b99011	2025-03-14 22:45:29.932703
3	pathtoken-column	2cb1b0004b817b29d5b0a971af16bafeede4b70d	2025-03-14 22:45:29.958835
4	add-migrations-rls	427c5b63fe1c5937495d9c635c263ee7a5905058	2025-03-14 22:45:29.991227
5	add-size-functions	79e081a1455b63666c1294a440f8ad4b1e6a7f84	2025-03-14 22:45:30.000478
6	change-column-name-in-get-size	f93f62afdf6613ee5e7e815b30d02dc990201044	2025-03-14 22:45:30.006336
7	add-rls-to-buckets	e7e7f86adbc51049f341dfe8d30256c1abca17aa	2025-03-14 22:45:30.012871
8	add-public-to-buckets	fd670db39ed65f9d08b01db09d6202503ca2bab3	2025-03-14 22:45:30.018427
9	fix-search-function	3a0af29f42e35a4d101c259ed955b67e1bee6825	2025-03-14 22:45:30.024866
10	search-files-search-function	68dc14822daad0ffac3746a502234f486182ef6e	2025-03-14 22:45:30.030788
11	add-trigger-to-auto-update-updated_at-column	7425bdb14366d1739fa8a18c83100636d74dcaa2	2025-03-14 22:45:30.037487
12	add-automatic-avif-detection-flag	8e92e1266eb29518b6a4c5313ab8f29dd0d08df9	2025-03-14 22:45:30.044612
13	add-bucket-custom-limits	cce962054138135cd9a8c4bcd531598684b25e7d	2025-03-14 22:45:30.052134
14	use-bytes-for-max-size	941c41b346f9802b411f06f30e972ad4744dad27	2025-03-14 22:45:30.06352
15	add-can-insert-object-function	934146bc38ead475f4ef4b555c524ee5d66799e5	2025-03-14 22:45:30.093591
16	add-version	76debf38d3fd07dcfc747ca49096457d95b1221b	2025-03-14 22:45:30.099528
17	drop-owner-foreign-key	f1cbb288f1b7a4c1eb8c38504b80ae2a0153d101	2025-03-14 22:45:30.105465
18	add_owner_id_column_deprecate_owner	e7a511b379110b08e2f214be852c35414749fe66	2025-03-14 22:45:30.113577
19	alter-default-value-objects-id	02e5e22a78626187e00d173dc45f58fa66a4f043	2025-03-14 22:45:30.120615
20	list-objects-with-delimiter	cd694ae708e51ba82bf012bba00caf4f3b6393b7	2025-03-14 22:45:30.126735
21	s3-multipart-uploads	8c804d4a566c40cd1e4cc5b3725a664a9303657f	2025-03-14 22:45:30.137815
22	s3-multipart-uploads-big-ints	9737dc258d2397953c9953d9b86920b8be0cdb73	2025-03-14 22:45:30.169897
23	optimize-search-function	9d7e604cddc4b56a5422dc68c9313f4a1b6f132c	2025-03-14 22:45:30.195499
24	operation-function	8312e37c2bf9e76bbe841aa5fda889206d2bf8aa	2025-03-14 22:45:30.201865
25	custom-metadata	67eb93b7e8d401cafcdc97f9ac779e71a79bfe03	2025-03-14 22:45:30.208396
\.


--
-- Data for Name: objects; Type: TABLE DATA; Schema: storage; Owner: -
--

COPY storage.objects (id, bucket_id, name, owner, created_at, updated_at, last_accessed_at, metadata, version, owner_id, user_metadata) FROM stdin;
369271cd-c67a-42df-bb60-12aa49b026ae	userphotoprofile	.emptyFolderPlaceholder	\N	2025-04-09 19:36:50.180209+00	2025-04-09 19:36:50.180209+00	2025-04-09 19:36:50.180209+00	{"eTag": "\\"d41d8cd98f00b204e9800998ecf8427e\\"", "size": 0, "mimetype": "application/octet-stream", "cacheControl": "max-age=3600", "lastModified": "2025-04-09T19:36:51.000Z", "contentLength": 0, "httpStatusCode": 200}	cdc66eba-2a1e-4e37-965d-eacc02d88615	\N	{}
cecfb751-b6f2-4196-9c97-57c56dd1bc22	userphotoprofile	auth0_67d5d64d64ccf1c522a6950b_df0d375618ad4f6896dd28ece0c5021f.jpeg	\N	2025-04-09 19:37:50.45873+00	2025-04-09 19:37:50.45873+00	2025-04-09 19:37:50.45873+00	{"eTag": "\\"b3e6389e7528eb0979412600d11a5323-2\\"", "size": 5600021, "mimetype": "image/jpeg", "cacheControl": "no-cache", "lastModified": "2025-04-09T19:37:51.000Z", "contentLength": 5600021, "httpStatusCode": 200}	9bf4e513-8c90-435f-a8b0-ccb7e3ef0874	\N	{}
2854af34-84dc-4c74-a8ad-eb02a02d9e78	userphotoprofile	auth0_67ef66dfcb9e2a66485f2dde_e7e7d67372fb40148f13b1df8c6d5284.png	\N	2025-04-12 19:36:07.794681+00	2025-04-12 19:36:07.794681+00	2025-04-12 19:36:07.794681+00	{"eTag": "\\"0287a6e7d21d5d0e2e7d6ee9af892b61-2\\"", "size": 5755990, "mimetype": "image/png", "cacheControl": "no-cache", "lastModified": "2025-04-12T19:36:08.000Z", "contentLength": 5755990, "httpStatusCode": 200}	36a2812a-cbc7-4e1f-aeae-d504a1e0de2f	\N	{}
c8f0761b-dfc5-4311-8475-c8e024933b47	userphotoprofile	auth0_67f71e304b8a05024c163e04_71e37e93cd5c4ae7b4ec9d25a3768833.png	\N	2025-04-13 06:12:28.205272+00	2025-04-13 06:12:28.205272+00	2025-04-13 06:12:28.205272+00	{"eTag": "\\"82c969a59603abeec19b6f80e0566e5f\\"", "size": 1108427, "mimetype": "image/png", "cacheControl": "no-cache", "lastModified": "2025-04-13T06:12:29.000Z", "contentLength": 1108427, "httpStatusCode": 200}	0dfb9357-20c3-4c7e-8792-3e7c9f7f222e	\N	{}
\.


--
-- Data for Name: s3_multipart_uploads; Type: TABLE DATA; Schema: storage; Owner: -
--

COPY storage.s3_multipart_uploads (id, in_progress_size, upload_signature, bucket_id, key, version, owner_id, created_at, user_metadata) FROM stdin;
\.


--
-- Data for Name: s3_multipart_uploads_parts; Type: TABLE DATA; Schema: storage; Owner: -
--

COPY storage.s3_multipart_uploads_parts (id, upload_id, size, part_number, bucket_id, key, etag, owner_id, version, created_at) FROM stdin;
\.


--
-- Data for Name: secrets; Type: TABLE DATA; Schema: vault; Owner: -
--

COPY vault.secrets (id, name, description, secret, key_id, nonce, created_at, updated_at) FROM stdin;
\.


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE SET; Schema: auth; Owner: -
--

SELECT pg_catalog.setval('auth.refresh_tokens_id_seq', 1, false);


--
-- Name: key_key_id_seq; Type: SEQUENCE SET; Schema: pgsodium; Owner: -
--

SELECT pg_catalog.setval('pgsodium.key_key_id_seq', 1, false);


--
-- Name: chat_members_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.chat_members_id_seq', 59, true);


--
-- Name: chat_rooms_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.chat_rooms_id_seq', 53, true);


--
-- Name: class_category_custom_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.class_category_custom_id_seq', 5, true);


--
-- Name: class_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.class_id_seq', 105, true);


--
-- Name: class_participation_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.class_participation_id_seq', 1, false);


--
-- Name: class_session_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.class_session_id_seq', 407, true);


--
-- Name: event_participations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.event_participations_id_seq', 39, true);


--
-- Name: events_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.events_id_seq', 51, true);


--
-- Name: gym_hours_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.gym_hours_id_seq', 16, true);


--
-- Name: gym_special_hours_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.gym_special_hours_id_seq', 14, true);


--
-- Name: gyms_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.gyms_id_seq', 2, true);


--
-- Name: trainermemberrelationship_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.trainermemberrelationship_id_seq', 1, false);


--
-- Name: user_gyms_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.user_gyms_id_seq', 5, true);


--
-- Name: user_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.user_id_seq', 8, true);


--
-- Name: subscription_id_seq; Type: SEQUENCE SET; Schema: realtime; Owner: -
--

SELECT pg_catalog.setval('realtime.subscription_id_seq', 1, false);


--
-- Name: mfa_amr_claims amr_id_pk; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT amr_id_pk PRIMARY KEY (id);


--
-- Name: audit_log_entries audit_log_entries_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.audit_log_entries
    ADD CONSTRAINT audit_log_entries_pkey PRIMARY KEY (id);


--
-- Name: flow_state flow_state_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.flow_state
    ADD CONSTRAINT flow_state_pkey PRIMARY KEY (id);


--
-- Name: identities identities_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_pkey PRIMARY KEY (id);


--
-- Name: identities identities_provider_id_provider_unique; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_provider_id_provider_unique UNIQUE (provider_id, provider);


--
-- Name: instances instances_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.instances
    ADD CONSTRAINT instances_pkey PRIMARY KEY (id);


--
-- Name: mfa_amr_claims mfa_amr_claims_session_id_authentication_method_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT mfa_amr_claims_session_id_authentication_method_pkey UNIQUE (session_id, authentication_method);


--
-- Name: mfa_challenges mfa_challenges_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_challenges
    ADD CONSTRAINT mfa_challenges_pkey PRIMARY KEY (id);


--
-- Name: mfa_factors mfa_factors_last_challenged_at_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_last_challenged_at_key UNIQUE (last_challenged_at);


--
-- Name: mfa_factors mfa_factors_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_pkey PRIMARY KEY (id);


--
-- Name: one_time_tokens one_time_tokens_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.one_time_tokens
    ADD CONSTRAINT one_time_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_token_unique; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_token_unique UNIQUE (token);


--
-- Name: saml_providers saml_providers_entity_id_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_entity_id_key UNIQUE (entity_id);


--
-- Name: saml_providers saml_providers_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_pkey PRIMARY KEY (id);


--
-- Name: saml_relay_states saml_relay_states_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (id);


--
-- Name: sso_domains sso_domains_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sso_domains
    ADD CONSTRAINT sso_domains_pkey PRIMARY KEY (id);


--
-- Name: sso_providers sso_providers_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sso_providers
    ADD CONSTRAINT sso_providers_pkey PRIMARY KEY (id);


--
-- Name: users users_phone_key; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_phone_key UNIQUE (phone);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: chat_members chat_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_members
    ADD CONSTRAINT chat_members_pkey PRIMARY KEY (id);


--
-- Name: chat_rooms chat_rooms_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_rooms
    ADD CONSTRAINT chat_rooms_pkey PRIMARY KEY (id);


--
-- Name: class_category_custom class_category_custom_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_category_custom
    ADD CONSTRAINT class_category_custom_pkey PRIMARY KEY (id);


--
-- Name: class_participation class_participation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_participation
    ADD CONSTRAINT class_participation_pkey PRIMARY KEY (id);


--
-- Name: class class_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class
    ADD CONSTRAINT class_pkey PRIMARY KEY (id);


--
-- Name: class_session class_session_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_session
    ADD CONSTRAINT class_session_pkey PRIMARY KEY (id);


--
-- Name: device_tokens device_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_tokens
    ADD CONSTRAINT device_tokens_pkey PRIMARY KEY (id);


--
-- Name: event_participations event_participations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_participations
    ADD CONSTRAINT event_participations_pkey PRIMARY KEY (id);


--
-- Name: events events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_pkey PRIMARY KEY (id);


--
-- Name: gym_hours gym_hours_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gym_hours
    ADD CONSTRAINT gym_hours_pkey PRIMARY KEY (id);


--
-- Name: gym_special_hours gym_special_hours_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gym_special_hours
    ADD CONSTRAINT gym_special_hours_pkey PRIMARY KEY (id);


--
-- Name: gyms gyms_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gyms
    ADD CONSTRAINT gyms_pkey PRIMARY KEY (id);


--
-- Name: trainermemberrelationship trainermemberrelationship_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trainermemberrelationship
    ADD CONSTRAINT trainermemberrelationship_pkey PRIMARY KEY (id);


--
-- Name: gym_special_hours uq_gym_special_hours_gym_date; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gym_special_hours
    ADD CONSTRAINT uq_gym_special_hours_gym_date UNIQUE (gym_id, date);


--
-- Name: device_tokens uq_user_device_token; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_tokens
    ADD CONSTRAINT uq_user_device_token UNIQUE (user_id, device_token);


--
-- Name: user_gyms uq_user_gym; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_gyms
    ADD CONSTRAINT uq_user_gym UNIQUE (user_id, gym_id);


--
-- Name: user_gyms user_gyms_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_gyms
    ADD CONSTRAINT user_gyms_pkey PRIMARY KEY (id);


--
-- Name: user user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_pkey PRIMARY KEY (id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id, inserted_at);


--
-- Name: subscription pk_subscription; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.subscription
    ADD CONSTRAINT pk_subscription PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: realtime; Owner: -
--

ALTER TABLE ONLY realtime.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: buckets buckets_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.buckets
    ADD CONSTRAINT buckets_pkey PRIMARY KEY (id);


--
-- Name: migrations migrations_name_key; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.migrations
    ADD CONSTRAINT migrations_name_key UNIQUE (name);


--
-- Name: migrations migrations_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.migrations
    ADD CONSTRAINT migrations_pkey PRIMARY KEY (id);


--
-- Name: objects objects_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.objects
    ADD CONSTRAINT objects_pkey PRIMARY KEY (id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_pkey PRIMARY KEY (id);


--
-- Name: s3_multipart_uploads s3_multipart_uploads_pkey; Type: CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.s3_multipart_uploads
    ADD CONSTRAINT s3_multipart_uploads_pkey PRIMARY KEY (id);


--
-- Name: audit_logs_instance_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX audit_logs_instance_id_idx ON auth.audit_log_entries USING btree (instance_id);


--
-- Name: confirmation_token_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX confirmation_token_idx ON auth.users USING btree (confirmation_token) WHERE ((confirmation_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: email_change_token_current_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX email_change_token_current_idx ON auth.users USING btree (email_change_token_current) WHERE ((email_change_token_current)::text !~ '^[0-9 ]*$'::text);


--
-- Name: email_change_token_new_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX email_change_token_new_idx ON auth.users USING btree (email_change_token_new) WHERE ((email_change_token_new)::text !~ '^[0-9 ]*$'::text);


--
-- Name: factor_id_created_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX factor_id_created_at_idx ON auth.mfa_factors USING btree (user_id, created_at);


--
-- Name: flow_state_created_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX flow_state_created_at_idx ON auth.flow_state USING btree (created_at DESC);


--
-- Name: identities_email_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX identities_email_idx ON auth.identities USING btree (email text_pattern_ops);


--
-- Name: INDEX identities_email_idx; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON INDEX auth.identities_email_idx IS 'Auth: Ensures indexed queries on the email column';


--
-- Name: identities_user_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX identities_user_id_idx ON auth.identities USING btree (user_id);


--
-- Name: idx_auth_code; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_auth_code ON auth.flow_state USING btree (auth_code);


--
-- Name: idx_user_id_auth_method; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX idx_user_id_auth_method ON auth.flow_state USING btree (user_id, authentication_method);


--
-- Name: mfa_challenge_created_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX mfa_challenge_created_at_idx ON auth.mfa_challenges USING btree (created_at DESC);


--
-- Name: mfa_factors_user_friendly_name_unique; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX mfa_factors_user_friendly_name_unique ON auth.mfa_factors USING btree (friendly_name, user_id) WHERE (TRIM(BOTH FROM friendly_name) <> ''::text);


--
-- Name: mfa_factors_user_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX mfa_factors_user_id_idx ON auth.mfa_factors USING btree (user_id);


--
-- Name: one_time_tokens_relates_to_hash_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX one_time_tokens_relates_to_hash_idx ON auth.one_time_tokens USING hash (relates_to);


--
-- Name: one_time_tokens_token_hash_hash_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX one_time_tokens_token_hash_hash_idx ON auth.one_time_tokens USING hash (token_hash);


--
-- Name: one_time_tokens_user_id_token_type_key; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX one_time_tokens_user_id_token_type_key ON auth.one_time_tokens USING btree (user_id, token_type);


--
-- Name: reauthentication_token_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX reauthentication_token_idx ON auth.users USING btree (reauthentication_token) WHERE ((reauthentication_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: recovery_token_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX recovery_token_idx ON auth.users USING btree (recovery_token) WHERE ((recovery_token)::text !~ '^[0-9 ]*$'::text);


--
-- Name: refresh_tokens_instance_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX refresh_tokens_instance_id_idx ON auth.refresh_tokens USING btree (instance_id);


--
-- Name: refresh_tokens_instance_id_user_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX refresh_tokens_instance_id_user_id_idx ON auth.refresh_tokens USING btree (instance_id, user_id);


--
-- Name: refresh_tokens_parent_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX refresh_tokens_parent_idx ON auth.refresh_tokens USING btree (parent);


--
-- Name: refresh_tokens_session_id_revoked_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX refresh_tokens_session_id_revoked_idx ON auth.refresh_tokens USING btree (session_id, revoked);


--
-- Name: refresh_tokens_updated_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX refresh_tokens_updated_at_idx ON auth.refresh_tokens USING btree (updated_at DESC);


--
-- Name: saml_providers_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX saml_providers_sso_provider_id_idx ON auth.saml_providers USING btree (sso_provider_id);


--
-- Name: saml_relay_states_created_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX saml_relay_states_created_at_idx ON auth.saml_relay_states USING btree (created_at DESC);


--
-- Name: saml_relay_states_for_email_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX saml_relay_states_for_email_idx ON auth.saml_relay_states USING btree (for_email);


--
-- Name: saml_relay_states_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX saml_relay_states_sso_provider_id_idx ON auth.saml_relay_states USING btree (sso_provider_id);


--
-- Name: sessions_not_after_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX sessions_not_after_idx ON auth.sessions USING btree (not_after DESC);


--
-- Name: sessions_user_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX sessions_user_id_idx ON auth.sessions USING btree (user_id);


--
-- Name: sso_domains_domain_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX sso_domains_domain_idx ON auth.sso_domains USING btree (lower(domain));


--
-- Name: sso_domains_sso_provider_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX sso_domains_sso_provider_id_idx ON auth.sso_domains USING btree (sso_provider_id);


--
-- Name: sso_providers_resource_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX sso_providers_resource_id_idx ON auth.sso_providers USING btree (lower(resource_id));


--
-- Name: unique_phone_factor_per_user; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX unique_phone_factor_per_user ON auth.mfa_factors USING btree (user_id, phone);


--
-- Name: user_id_created_at_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX user_id_created_at_idx ON auth.sessions USING btree (user_id, created_at);


--
-- Name: users_email_partial_key; Type: INDEX; Schema: auth; Owner: -
--

CREATE UNIQUE INDEX users_email_partial_key ON auth.users USING btree (email) WHERE (is_sso_user = false);


--
-- Name: INDEX users_email_partial_key; Type: COMMENT; Schema: auth; Owner: -
--

COMMENT ON INDEX auth.users_email_partial_key IS 'Auth: A partial unique index that applies only when is_sso_user is false';


--
-- Name: users_instance_id_email_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX users_instance_id_email_idx ON auth.users USING btree (instance_id, lower((email)::text));


--
-- Name: users_instance_id_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX users_instance_id_idx ON auth.users USING btree (instance_id);


--
-- Name: users_is_anonymous_idx; Type: INDEX; Schema: auth; Owner: -
--

CREATE INDEX users_is_anonymous_idx ON auth.users USING btree (is_anonymous);


--
-- Name: idx_device_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_device_token ON public.device_tokens USING btree (device_token);


--
-- Name: ix_chat_members_auth0_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_members_auth0_user_id ON public.chat_members USING btree (auth0_user_id);


--
-- Name: ix_chat_members_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_members_id ON public.chat_members USING btree (id);


--
-- Name: ix_chat_members_user_id_room_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_members_user_id_room_id ON public.chat_members USING btree (user_id, room_id);


--
-- Name: ix_chat_rooms_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_rooms_event_id ON public.chat_rooms USING btree (event_id);


--
-- Name: ix_chat_rooms_event_id_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_rooms_event_id_type ON public.chat_rooms USING btree (event_id, stream_channel_type);


--
-- Name: ix_chat_rooms_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_rooms_id ON public.chat_rooms USING btree (id);


--
-- Name: ix_chat_rooms_is_direct; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_rooms_is_direct ON public.chat_rooms USING btree (is_direct);


--
-- Name: ix_chat_rooms_stream_channel_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_chat_rooms_stream_channel_id ON public.chat_rooms USING btree (stream_channel_id);


--
-- Name: ix_class_category_custom_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_class_category_custom_id ON public.class_category_custom USING btree (id);


--
-- Name: ix_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_class_id ON public.class USING btree (id);


--
-- Name: ix_class_participation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_class_participation_id ON public.class_participation USING btree (id);


--
-- Name: ix_class_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_class_session_id ON public.class_session USING btree (id);


--
-- Name: ix_class_session_start_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_class_session_start_time ON public.class_session USING btree (start_time);


--
-- Name: ix_device_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_device_tokens_user_id ON public.device_tokens USING btree (user_id);


--
-- Name: ix_event_participation_event_member; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_participation_event_member ON public.event_participations USING btree (event_id, member_id);


--
-- Name: ix_event_participation_gym_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_participation_gym_status ON public.event_participations USING btree (gym_id, status);


--
-- Name: ix_event_participations_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_participations_event_id ON public.event_participations USING btree (event_id);


--
-- Name: ix_event_participations_gym_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_participations_gym_id ON public.event_participations USING btree (gym_id);


--
-- Name: ix_event_participations_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_participations_id ON public.event_participations USING btree (id);


--
-- Name: ix_event_participations_member_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_participations_member_id ON public.event_participations USING btree (member_id);


--
-- Name: ix_event_participations_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_participations_status ON public.event_participations USING btree (status);


--
-- Name: ix_events_creator_gym; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_events_creator_gym ON public.events USING btree (creator_id, gym_id);


--
-- Name: ix_events_creator_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_events_creator_id ON public.events USING btree (creator_id);


--
-- Name: ix_events_end_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_events_end_time ON public.events USING btree (end_time);


--
-- Name: ix_events_gym_dates; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_events_gym_dates ON public.events USING btree (gym_id, start_time, end_time);


--
-- Name: ix_events_gym_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_events_gym_id ON public.events USING btree (gym_id);


--
-- Name: ix_events_gym_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_events_gym_status ON public.events USING btree (gym_id, status);


--
-- Name: ix_events_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_events_id ON public.events USING btree (id);


--
-- Name: ix_events_start_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_events_start_time ON public.events USING btree (start_time);


--
-- Name: ix_events_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_events_status ON public.events USING btree (status);


--
-- Name: ix_gym_hours_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_gym_hours_id ON public.gym_hours USING btree (id);


--
-- Name: ix_gym_special_hours_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_gym_special_hours_date ON public.gym_special_hours USING btree (date);


--
-- Name: ix_gym_special_hours_gym_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_gym_special_hours_gym_id ON public.gym_special_hours USING btree (gym_id);


--
-- Name: ix_gym_special_hours_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_gym_special_hours_id ON public.gym_special_hours USING btree (id);


--
-- Name: ix_gyms_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_gyms_id ON public.gyms USING btree (id);


--
-- Name: ix_gyms_subdomain; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_gyms_subdomain ON public.gyms USING btree (subdomain);


--
-- Name: ix_trainermemberrelationship_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trainermemberrelationship_id ON public.trainermemberrelationship USING btree (id);


--
-- Name: ix_user_auth0_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_user_auth0_id ON public."user" USING btree (auth0_id);


--
-- Name: ix_user_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_user_email ON public."user" USING btree (email);


--
-- Name: ix_user_first_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_first_name ON public."user" USING btree (first_name);


--
-- Name: ix_user_gyms_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_gyms_id ON public.user_gyms USING btree (id);


--
-- Name: ix_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_id ON public."user" USING btree (id);


--
-- Name: ix_user_last_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_last_name ON public."user" USING btree (last_name);


--
-- Name: ix_realtime_subscription_entity; Type: INDEX; Schema: realtime; Owner: -
--

CREATE INDEX ix_realtime_subscription_entity ON realtime.subscription USING btree (entity);


--
-- Name: subscription_subscription_id_entity_filters_key; Type: INDEX; Schema: realtime; Owner: -
--

CREATE UNIQUE INDEX subscription_subscription_id_entity_filters_key ON realtime.subscription USING btree (subscription_id, entity, filters);


--
-- Name: bname; Type: INDEX; Schema: storage; Owner: -
--

CREATE UNIQUE INDEX bname ON storage.buckets USING btree (name);


--
-- Name: bucketid_objname; Type: INDEX; Schema: storage; Owner: -
--

CREATE UNIQUE INDEX bucketid_objname ON storage.objects USING btree (bucket_id, name);


--
-- Name: idx_multipart_uploads_list; Type: INDEX; Schema: storage; Owner: -
--

CREATE INDEX idx_multipart_uploads_list ON storage.s3_multipart_uploads USING btree (bucket_id, key, created_at);


--
-- Name: idx_objects_bucket_id_name; Type: INDEX; Schema: storage; Owner: -
--

CREATE INDEX idx_objects_bucket_id_name ON storage.objects USING btree (bucket_id, name COLLATE "C");


--
-- Name: name_prefix_search; Type: INDEX; Schema: storage; Owner: -
--

CREATE INDEX name_prefix_search ON storage.objects USING btree (name text_pattern_ops);


--
-- Name: subscription tr_check_filters; Type: TRIGGER; Schema: realtime; Owner: -
--

CREATE TRIGGER tr_check_filters BEFORE INSERT OR UPDATE ON realtime.subscription FOR EACH ROW EXECUTE FUNCTION realtime.subscription_check_filters();


--
-- Name: objects update_objects_updated_at; Type: TRIGGER; Schema: storage; Owner: -
--

CREATE TRIGGER update_objects_updated_at BEFORE UPDATE ON storage.objects FOR EACH ROW EXECUTE FUNCTION storage.update_updated_at_column();


--
-- Name: identities identities_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.identities
    ADD CONSTRAINT identities_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: mfa_amr_claims mfa_amr_claims_session_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_amr_claims
    ADD CONSTRAINT mfa_amr_claims_session_id_fkey FOREIGN KEY (session_id) REFERENCES auth.sessions(id) ON DELETE CASCADE;


--
-- Name: mfa_challenges mfa_challenges_auth_factor_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_challenges
    ADD CONSTRAINT mfa_challenges_auth_factor_id_fkey FOREIGN KEY (factor_id) REFERENCES auth.mfa_factors(id) ON DELETE CASCADE;


--
-- Name: mfa_factors mfa_factors_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.mfa_factors
    ADD CONSTRAINT mfa_factors_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: one_time_tokens one_time_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.one_time_tokens
    ADD CONSTRAINT one_time_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: refresh_tokens refresh_tokens_session_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.refresh_tokens
    ADD CONSTRAINT refresh_tokens_session_id_fkey FOREIGN KEY (session_id) REFERENCES auth.sessions(id) ON DELETE CASCADE;


--
-- Name: saml_providers saml_providers_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_providers
    ADD CONSTRAINT saml_providers_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: saml_relay_states saml_relay_states_flow_state_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_flow_state_id_fkey FOREIGN KEY (flow_state_id) REFERENCES auth.flow_state(id) ON DELETE CASCADE;


--
-- Name: saml_relay_states saml_relay_states_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.saml_relay_states
    ADD CONSTRAINT saml_relay_states_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: sessions sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sessions
    ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- Name: sso_domains sso_domains_sso_provider_id_fkey; Type: FK CONSTRAINT; Schema: auth; Owner: -
--

ALTER TABLE ONLY auth.sso_domains
    ADD CONSTRAINT sso_domains_sso_provider_id_fkey FOREIGN KEY (sso_provider_id) REFERENCES auth.sso_providers(id) ON DELETE CASCADE;


--
-- Name: chat_members chat_members_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_members
    ADD CONSTRAINT chat_members_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.chat_rooms(id);


--
-- Name: chat_rooms chat_rooms_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_rooms
    ADD CONSTRAINT chat_rooms_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id);


--
-- Name: class_category_custom class_category_custom_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_category_custom
    ADD CONSTRAINT class_category_custom_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: class_category_custom class_category_custom_gym_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_category_custom
    ADD CONSTRAINT class_category_custom_gym_id_fkey FOREIGN KEY (gym_id) REFERENCES public.gyms(id);


--
-- Name: class class_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class
    ADD CONSTRAINT class_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.class_category_custom(id);


--
-- Name: class class_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class
    ADD CONSTRAINT class_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: class class_gym_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class
    ADD CONSTRAINT class_gym_id_fkey FOREIGN KEY (gym_id) REFERENCES public.gyms(id);


--
-- Name: class_participation class_participation_gym_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_participation
    ADD CONSTRAINT class_participation_gym_id_fkey FOREIGN KEY (gym_id) REFERENCES public.gyms(id);


--
-- Name: class_participation class_participation_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_participation
    ADD CONSTRAINT class_participation_member_id_fkey FOREIGN KEY (member_id) REFERENCES public."user"(id);


--
-- Name: class_participation class_participation_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_participation
    ADD CONSTRAINT class_participation_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.class_session(id);


--
-- Name: class_session class_session_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_session
    ADD CONSTRAINT class_session_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.class(id);


--
-- Name: class_session class_session_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_session
    ADD CONSTRAINT class_session_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: class_session class_session_trainer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_session
    ADD CONSTRAINT class_session_trainer_id_fkey FOREIGN KEY (trainer_id) REFERENCES public."user"(id);


--
-- Name: event_participations event_participations_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_participations
    ADD CONSTRAINT event_participations_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.events(id);


--
-- Name: event_participations event_participations_gym_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_participations
    ADD CONSTRAINT event_participations_gym_id_fkey FOREIGN KEY (gym_id) REFERENCES public.gyms(id);


--
-- Name: event_participations event_participations_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_participations
    ADD CONSTRAINT event_participations_member_id_fkey FOREIGN KEY (member_id) REFERENCES public."user"(id);


--
-- Name: events events_creator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_creator_id_fkey FOREIGN KEY (creator_id) REFERENCES public."user"(id);


--
-- Name: events events_gym_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.events
    ADD CONSTRAINT events_gym_id_fkey FOREIGN KEY (gym_id) REFERENCES public.gyms(id);


--
-- Name: chat_members fk_chat_members_user_id_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_members
    ADD CONSTRAINT fk_chat_members_user_id_user FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: class_session fk_class_session_gym_id_gyms; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_session
    ADD CONSTRAINT fk_class_session_gym_id_gyms FOREIGN KEY (gym_id) REFERENCES public.gyms(id);


--
-- Name: gym_hours gym_hours_gym_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gym_hours
    ADD CONSTRAINT gym_hours_gym_id_fkey FOREIGN KEY (gym_id) REFERENCES public.gyms(id);


--
-- Name: gym_special_hours gym_special_hours_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gym_special_hours
    ADD CONSTRAINT gym_special_hours_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: gym_special_hours gym_special_hours_gym_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gym_special_hours
    ADD CONSTRAINT gym_special_hours_gym_id_fkey FOREIGN KEY (gym_id) REFERENCES public.gyms(id);


--
-- Name: trainermemberrelationship trainermemberrelationship_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trainermemberrelationship
    ADD CONSTRAINT trainermemberrelationship_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: trainermemberrelationship trainermemberrelationship_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trainermemberrelationship
    ADD CONSTRAINT trainermemberrelationship_member_id_fkey FOREIGN KEY (member_id) REFERENCES public."user"(id);


--
-- Name: trainermemberrelationship trainermemberrelationship_trainer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trainermemberrelationship
    ADD CONSTRAINT trainermemberrelationship_trainer_id_fkey FOREIGN KEY (trainer_id) REFERENCES public."user"(id);


--
-- Name: user_gyms user_gyms_gym_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_gyms
    ADD CONSTRAINT user_gyms_gym_id_fkey FOREIGN KEY (gym_id) REFERENCES public.gyms(id);


--
-- Name: user_gyms user_gyms_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_gyms
    ADD CONSTRAINT user_gyms_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: objects objects_bucketId_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.objects
    ADD CONSTRAINT "objects_bucketId_fkey" FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads s3_multipart_uploads_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.s3_multipart_uploads
    ADD CONSTRAINT s3_multipart_uploads_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_bucket_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_bucket_id_fkey FOREIGN KEY (bucket_id) REFERENCES storage.buckets(id);


--
-- Name: s3_multipart_uploads_parts s3_multipart_uploads_parts_upload_id_fkey; Type: FK CONSTRAINT; Schema: storage; Owner: -
--

ALTER TABLE ONLY storage.s3_multipart_uploads_parts
    ADD CONSTRAINT s3_multipart_uploads_parts_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES storage.s3_multipart_uploads(id) ON DELETE CASCADE;


--
-- Name: audit_log_entries; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.audit_log_entries ENABLE ROW LEVEL SECURITY;

--
-- Name: flow_state; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.flow_state ENABLE ROW LEVEL SECURITY;

--
-- Name: identities; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.identities ENABLE ROW LEVEL SECURITY;

--
-- Name: instances; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.instances ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_amr_claims; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.mfa_amr_claims ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_challenges; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.mfa_challenges ENABLE ROW LEVEL SECURITY;

--
-- Name: mfa_factors; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.mfa_factors ENABLE ROW LEVEL SECURITY;

--
-- Name: one_time_tokens; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.one_time_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: refresh_tokens; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.refresh_tokens ENABLE ROW LEVEL SECURITY;

--
-- Name: saml_providers; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.saml_providers ENABLE ROW LEVEL SECURITY;

--
-- Name: saml_relay_states; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.saml_relay_states ENABLE ROW LEVEL SECURITY;

--
-- Name: schema_migrations; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.schema_migrations ENABLE ROW LEVEL SECURITY;

--
-- Name: sessions; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.sessions ENABLE ROW LEVEL SECURITY;

--
-- Name: sso_domains; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.sso_domains ENABLE ROW LEVEL SECURITY;

--
-- Name: sso_providers; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.sso_providers ENABLE ROW LEVEL SECURITY;

--
-- Name: users; Type: ROW SECURITY; Schema: auth; Owner: -
--

ALTER TABLE auth.users ENABLE ROW LEVEL SECURITY;

--
-- Name: messages; Type: ROW SECURITY; Schema: realtime; Owner: -
--

ALTER TABLE realtime.messages ENABLE ROW LEVEL SECURITY;

--
-- Name: buckets; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.buckets ENABLE ROW LEVEL SECURITY;

--
-- Name: migrations; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.migrations ENABLE ROW LEVEL SECURITY;

--
-- Name: objects; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

--
-- Name: s3_multipart_uploads; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.s3_multipart_uploads ENABLE ROW LEVEL SECURITY;

--
-- Name: s3_multipart_uploads_parts; Type: ROW SECURITY; Schema: storage; Owner: -
--

ALTER TABLE storage.s3_multipart_uploads_parts ENABLE ROW LEVEL SECURITY;

--
-- Name: supabase_realtime; Type: PUBLICATION; Schema: -; Owner: -
--

CREATE PUBLICATION supabase_realtime WITH (publish = 'insert, update, delete, truncate');


--
-- Name: issue_graphql_placeholder; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER issue_graphql_placeholder ON sql_drop
         WHEN TAG IN ('DROP EXTENSION')
   EXECUTE FUNCTION extensions.set_graphql_placeholder();


--
-- Name: issue_pg_cron_access; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER issue_pg_cron_access ON ddl_command_end
         WHEN TAG IN ('CREATE EXTENSION')
   EXECUTE FUNCTION extensions.grant_pg_cron_access();


--
-- Name: issue_pg_graphql_access; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER issue_pg_graphql_access ON ddl_command_end
         WHEN TAG IN ('CREATE FUNCTION')
   EXECUTE FUNCTION extensions.grant_pg_graphql_access();


--
-- Name: issue_pg_net_access; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER issue_pg_net_access ON ddl_command_end
         WHEN TAG IN ('CREATE EXTENSION')
   EXECUTE FUNCTION extensions.grant_pg_net_access();


--
-- Name: pgrst_ddl_watch; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER pgrst_ddl_watch ON ddl_command_end
   EXECUTE FUNCTION extensions.pgrst_ddl_watch();


--
-- Name: pgrst_drop_watch; Type: EVENT TRIGGER; Schema: -; Owner: -
--

CREATE EVENT TRIGGER pgrst_drop_watch ON sql_drop
   EXECUTE FUNCTION extensions.pgrst_drop_watch();


--
-- PostgreSQL database dump complete
--

