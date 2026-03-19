-- Create the sequence
CREATE SEQUENCE IF NOT EXISTS hub_and_disc_assembly_schema.roles_role_id_seq
    INCREMENT 1
    START 1
    MINVALUE 1
    MAXVALUE 2147483647
    CACHE 1;

-- Create the table
CREATE TABLE IF NOT EXISTS hub_and_disc_assembly_schema.roles
(
    role_id integer NOT NULL DEFAULT nextval('hub_and_disc_assembly_schema.roles_role_id_seq'::regclass),
    role_name character varying(255) COLLATE pg_catalog."default" NOT NULL,
    modules_access character varying(255) COLLATE pg_catalog."default",
    CONSTRAINT roles_pkey PRIMARY KEY (role_id),
	CONSTRAINT roles_rolename_key UNIQUE (role_name)
);

-- Create the sequence
CREATE SEQUENCE IF NOT EXISTS hub_and_disc_assembly_schema.users_user_id_seq
    INCREMENT BY 1
    START WITH 100
    MINVALUE 1
    MAXVALUE 2147483647
    CACHE 1;

-- Create the table
CREATE TABLE IF NOT EXISTS hub_and_disc_assembly_schema.users
(
    user_id integer NOT NULL DEFAULT nextval('hub_and_disc_assembly_schema.users_user_id_seq'::regclass),
    username character varying(100) COLLATE pg_catalog."default" NOT NULL,
    password character varying(1024) COLLATE pg_catalog."default" NOT NULL,
    first_name character varying(100) COLLATE pg_catalog."default" NOT NULL,
    middle_name character varying(100) COLLATE pg_catalog."default",
    last_name character varying(100) COLLATE pg_catalog."default",
    role_name character varying(255) COLLATE pg_catalog."default" NOT NULL,
    email character varying(255) COLLATE pg_catalog."default",
    mobile character varying(255) COLLATE pg_catalog."default",
    active_status character varying(20) COLLATE pg_catalog."default" NOT NULL DEFAULT 'YES'::character varying,
    remarks character varying(255) COLLATE pg_catalog."default",
    created_on timestamp without time zone NOT NULL,
    last_login timestamp without time zone,
    CONSTRAINT users_pkey PRIMARY KEY (user_id),
    CONSTRAINT users_username_key UNIQUE (username),
    CONSTRAINT users_role_name_fkey FOREIGN KEY (role_name)
        REFERENCES hub_and_disc_assembly_schema.roles (role_name) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
);

-- Create the sequence
CREATE SEQUENCE IF NOT EXISTS hub_and_disc_assembly_schema.hub_and_disc_assembly_data_record_id_seq
    INCREMENT BY 1
    START WITH 1000
    MINVALUE 1
    MAXVALUE 2147483647
    CACHE 1;

-- Create the table
CREATE TABLE IF NOT EXISTS hub_and_disc_assembly_schema.hub_and_disc_assembly_data
(
    record_id integer NOT NULL DEFAULT nextval('hub_and_disc_assembly_schema.hub_and_disc_assembly_data_record_id_seq'::regclass),
    qr_code character varying(255) COLLATE pg_catalog."default" NOT NULL,
    model_name character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    model_tonnage character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    component_manufacturing_date timestamp without time zone,
    knuckle_check_imagefile character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    knuckle_check_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    bearing_check_imagefile character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    bearing_check_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    hub_and_second_bearing_check_imagefile character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    hub_and_second_bearing_check_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    nut_and_platewasher_check_imagefile character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    nut_and_platewasher_check_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    nut_tightening_torque_1 float DEFAULT -1.0 NOT NULL,
    free_rotation_torque_1 float DEFAULT -1.0 NOT NULL,
    nut_tightening_torque_2 float DEFAULT -1.0 NOT NULL,
    free_rotation_torque_2 float DEFAULT -1.0 NOT NULL,
    nut_tightening_torque_3 float DEFAULT -1.0 NOT NULL,
    free_rotation_torque_3 float DEFAULT -1.0 NOT NULL,
    splitpin_and_washer_check_imagefile character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    splitpin_and_washer_check_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    cap_check_imagefile character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    cap_check_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    bung_check_imagefile character varying(255) COLLATE pg_catalog."default" DEFAULT 'Not Populated',
    bung_check_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    cap_pressed_successfully_check_result character varying(15) COLLATE pg_catalog."default" NOT NULL DEFAULT 'Not Checked',
    ok_notok_result character varying(15) COLLATE pg_catalog."default" NOT NULL,
    username character varying(100) COLLATE pg_catalog."default" NOT NULL,
    remarks character varying(255) COLLATE pg_catalog."default",
    created_on timestamp without time zone NOT NULL,
    CONSTRAINT hub_and_disc_assembly_data_pkey PRIMARY KEY (record_id),
    CONSTRAINT hub_and_disc_assembly_data_username_fkey FOREIGN KEY (username)
        REFERENCES hub_and_disc_assembly_schema.users (username) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
);

