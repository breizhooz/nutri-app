--
-- PostgreSQL database dump
--

\restrict FwV2iptFWTJgyACgJvimAZJ4LJQOjitftc9pHzzpUriCzqWX3HjvJxhjJ9mX67I

-- Dumped from database version 16.13
-- Dumped by pg_dump version 16.13

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: nutriuser
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO nutriuser;

--
-- Name: mfa_pending_codes; Type: TABLE; Schema: public; Owner: nutriuser
--

CREATE TABLE public.mfa_pending_codes (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    code_hash character varying(255) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.mfa_pending_codes OWNER TO nutriuser;

--
-- Name: oauth_accounts; Type: TABLE; Schema: public; Owner: nutriuser
--

CREATE TABLE public.oauth_accounts (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    provider character varying(50) NOT NULL,
    provider_user_id character varying(255) NOT NULL,
    provider_email character varying(255),
    access_token character varying(2048),
    refresh_token character varying(2048),
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.oauth_accounts OWNER TO nutriuser;

--
-- Name: password_history; Type: TABLE; Schema: public; Owner: nutriuser
--

CREATE TABLE public.password_history (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    hashed_password character varying(255) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.password_history OWNER TO nutriuser;

--
-- Name: password_reset_tokens; Type: TABLE; Schema: public; Owner: nutriuser
--

CREATE TABLE public.password_reset_tokens (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    token_hash character varying(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.password_reset_tokens OWNER TO nutriuser;

--
-- Name: users; Type: TABLE; Schema: public; Owner: nutriuser
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    email character varying(255) NOT NULL,
    hashed_password character varying(255),
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    totp_secret character varying(255),
    two_factor_enabled boolean DEFAULT false NOT NULL,
    two_factor_method character varying(10),
    user_admin boolean DEFAULT false NOT NULL,
    user_right jsonb DEFAULT '{"crawl": {"web": false, "instagram": false}}'::jsonb NOT NULL
);


ALTER TABLE public.users OWNER TO nutriuser;

--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: nutriuser
--

COPY public.alembic_version (version_num) FROM stdin;
c3f9a1b2d4e5
\.


--
-- Data for Name: mfa_pending_codes; Type: TABLE DATA; Schema: public; Owner: nutriuser
--

COPY public.mfa_pending_codes (id, user_id, code_hash, expires_at, used_at, created_at) FROM stdin;
\.


--
-- Data for Name: oauth_accounts; Type: TABLE DATA; Schema: public; Owner: nutriuser
--

COPY public.oauth_accounts (id, user_id, provider, provider_user_id, provider_email, access_token, refresh_token, expires_at, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: password_history; Type: TABLE DATA; Schema: public; Owner: nutriuser
--

COPY public.password_history (id, user_id, hashed_password, created_at) FROM stdin;
\.


--
-- Data for Name: password_reset_tokens; Type: TABLE DATA; Schema: public; Owner: nutriuser
--

COPY public.password_reset_tokens (id, user_id, token_hash, expires_at, used_at, created_at) FROM stdin;
c54abf7c-2c52-4c36-a9ec-237f050ac5e2	2bb14ad7-4472-4ab6-bf9e-2d704a8d1dd6	818c8323a5faf4a1b81273ca993fac9032f982a0b9f155a80810a4999fafb78e	2026-05-27 10:45:03.56583+00	\N	2026-05-27 10:15:03.558338+00
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: nutriuser
--

COPY public.users (id, email, hashed_password, is_active, created_at, totp_secret, two_factor_enabled, two_factor_method, user_admin, user_right) FROM stdin;
2bb14ad7-4472-4ab6-bf9e-2d704a8d1dd6	breizhooz@gmail.com	$argon2id$v=19$m=65536,t=3,p=4$Xo31+qoM67/w/Hlaej1nsg$x3HfwpZimwswF3oxNPVh+vdtvSygw4g+z9L7B1V+huw	t	2026-05-25 20:29:44.311365+00	gAAAAABqGxgCEj-4yBsHEyPYW4nqbISdnk87COcBezmHrC2z63RiulQ-ElB6ypZk8ohc8sCBd9dk9nYApcw-QKpIZ8vXuvfuqissUHswgXVWiTBVw7BX8c1XqBaHPyrefayOitCf_aAn	f	\N	t	{"crawl": {"web": true, "instagram": true}, "uniq_link": {"web": false, "instagram": false}}
\.


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: nutriuser
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: mfa_pending_codes mfa_pending_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: nutriuser
--

ALTER TABLE ONLY public.mfa_pending_codes
    ADD CONSTRAINT mfa_pending_codes_pkey PRIMARY KEY (id);


--
-- Name: oauth_accounts oauth_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: nutriuser
--

ALTER TABLE ONLY public.oauth_accounts
    ADD CONSTRAINT oauth_accounts_pkey PRIMARY KEY (id);


--
-- Name: password_history password_history_pkey; Type: CONSTRAINT; Schema: public; Owner: nutriuser
--

ALTER TABLE ONLY public.password_history
    ADD CONSTRAINT password_history_pkey PRIMARY KEY (id);


--
-- Name: password_reset_tokens password_reset_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: nutriuser
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (id);


--
-- Name: oauth_accounts uq_oauth_provider_user; Type: CONSTRAINT; Schema: public; Owner: nutriuser
--

ALTER TABLE ONLY public.oauth_accounts
    ADD CONSTRAINT uq_oauth_provider_user UNIQUE (provider, provider_user_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: nutriuser
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_mfa_pending_codes_user_id; Type: INDEX; Schema: public; Owner: nutriuser
--

CREATE INDEX ix_mfa_pending_codes_user_id ON public.mfa_pending_codes USING btree (user_id);


--
-- Name: ix_oauth_accounts_user_id; Type: INDEX; Schema: public; Owner: nutriuser
--

CREATE INDEX ix_oauth_accounts_user_id ON public.oauth_accounts USING btree (user_id);


--
-- Name: ix_password_history_user_id; Type: INDEX; Schema: public; Owner: nutriuser
--

CREATE INDEX ix_password_history_user_id ON public.password_history USING btree (user_id);


--
-- Name: ix_password_reset_tokens_token_hash; Type: INDEX; Schema: public; Owner: nutriuser
--

CREATE UNIQUE INDEX ix_password_reset_tokens_token_hash ON public.password_reset_tokens USING btree (token_hash);


--
-- Name: ix_password_reset_tokens_user_id; Type: INDEX; Schema: public; Owner: nutriuser
--

CREATE INDEX ix_password_reset_tokens_user_id ON public.password_reset_tokens USING btree (user_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: nutriuser
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- PostgreSQL database dump complete
--

\unrestrict FwV2iptFWTJgyACgJvimAZJ4LJQOjitftc9pHzzpUriCzqWX3HjvJxhjJ9mX67I

