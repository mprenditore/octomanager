#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2021 Stefano Stella <mprenditore@gmail.com>
#
# Distributed under terms of the MIT license.

"""

"""
import sys
import os
import click
import yaml
from time import sleep

__author__ = "Stefano Stella"

_default_octoprint_exec = "octoprint"
_default_additional_options = ""
_default_start_timeout = 10
_default_stop_timeout = 10
_default_pid_path = "/tmp"
_vars_to_check = ["octoprint_exec", "additional_options"]


def wait_command_timeout(timeout, pid_file, wanted_status):
    while timeout > 0:
        if check_pidfile(pid_file) == wanted_status:
            return True
        else:
            sleep(1)
            timeout -= 1
    return False


def check_pidfile(pid_file):
    try:
        with open(pid_file, 'r') as f:
            pid = f.read()
        if not pid:
            os.system(f"rm -f {pid_file}")
            return False
    except IOError as e:
        return False
    except Exception:  # handle other exceptions such as attribute errors
        return False
    if pid_running(int(pid)):
        return True
    else:
        os.system(f"rm -f {pid_file}")
        return False


def pid_running(pid):
    """ Check for the existence of a Unix PID. """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def get_profile(ctx):
    profile_name = ctx.obj['profile_name']
    config = ctx.obj['config']
    config_file = ctx.obj['config_file']
    if profile_name not in config['profiles']:
        click.echo(f"[ERROR] Profile {profile_name} not found in {config_file}")
        sys.exit(1)
    click.echo(f"[DEBUG] Loaded profile for {profile_name}: {config['profiles'][profile_name]}")
    for var in _vars_to_check:
        if var in config['profiles'][profile_name]:
            ctx.obj[var] = config['profiles'][profile_name][var]
    return config['profiles'][profile_name]


def render_cmd(ctx, command):
    additional_options = ' '.join(ctx.obj['additional_options'])
    cmd = f"{ctx.obj['octoprint_exec']} daemon {additional_options}"
    args = ['host', 'port', 'config', 'basedir', 'logging']
    opts = ['verbose', 'safe', 'ignore-blacklist', 'debug',
            'iknowwhatimdoing', 'ipv6', 'ipv4']

    for opt in opts:
        if opt in ctx.obj['profile']:
            cmd += f" --{opt}"
    for arg in args:
        if arg in ctx.obj['profile']:
            cmd += f" --{arg} {ctx.obj['profile'][arg]}"
    cmd += f" --pid {ctx.obj['pid_file']} {command}"
    click.echo(f"[DEBUG] running: {cmd}")
    return cmd


def get_pid_filename(ctx, profile_name):
    return ctx.obj['profile'].get('pid',
            f"{_default_pid_path}/octoprint_{profile_name}.pid")


@click.group()
@click.pass_context
@click.option(
    '--config',
    '-c',
    default='config.yml',
    type=click.File('r')
)
def main(ctx, config):
    """ CLI tool to manage multiple octoprint instances. """
    ctx.ensure_object(dict)

    ctx.obj['config_file'] = config.name
    click.echo(f"[INFO] Loading config file '{config.name}'")
    ctx.obj['config'] = yaml.load(config.read(), Loader=yaml.FullLoader)
    ctx.obj['octoprint_exec'] = ctx.obj['config'].get('octoprint_exec',
                                                      _default_octoprint_exec)
    ctx.obj['additional_options'] = ctx.obj['config'].get('additional_options',
                                                       _default_additional_options)
    ctx.obj['start_timeout'] = ctx.obj['config'].get('start_timeout',
                                                     _default_start_timeout)
    ctx.obj['stop_timeout'] = ctx.obj['config'].get('stop_timeout',
                                                    _default_stop_timeout)
    if 'profiles' not in ctx.obj['config']:
        click.echo(f"[ERROR] No profile found in the config file '{config.name}'")
        ctx.exit(1)
    pass


@main.command()
@click.pass_context
@click.argument('profile_name')
def start(ctx, profile_name):
    """
    This start Octoprint for a specific printer profile
    """
    ctx.obj['profile_name'] = profile_name
    ctx.obj['profile'] = get_profile(ctx)
    ctx.obj['pid_file'] = get_pid_filename(ctx, profile_name)

    if check_pidfile(ctx.obj['pid_file']):
        click.echo(f"[WARNING] Octoprint for '{profile_name}' is already running")
        ctx.exit(0)
    click.echo("[DEBUG] Who am I:")
    os.system('whoami')
    os.system(render_cmd(ctx, 'start'))
    sleep(2)
    if wait_command_timeout(ctx.obj['start_timeout'], ctx.obj['pid_file'], True):
        click.echo(f"[INFO] Successfully to start Octoprint for '{profile_name}'")
        ctx.exit(0)
    click.echo(f"[ERROR] Failed to start Octoprint for '{profile_name}'")
    ctx.exit(1)


@main.command()
@click.pass_context
@click.argument('profile_name')
def stop(ctx, profile_name):
    """
    This stop Octoprint for a specific printer profile
    """
    ctx.obj['profile_name'] = profile_name
    ctx.obj['profile'] = get_profile(ctx)
    ctx.obj['pid_file'] = get_pid_filename(ctx, profile_name)

    if not check_pidfile(ctx.obj['pid_file']):
        click.echo(f"[WARNING] Octoprint for '{profile_name}' is already stopped")
        ctx.exit(0)
    os.system(render_cmd(ctx, 'stop'))
    if not wait_command_timeout(ctx.obj['stop_timeout'], ctx.obj['pid_file'], False):
        click.echo(f"[ERROR] Failed to stop Octoprint for '{profile_name}'")
        ctx.exit(1)
    click.echo(f"[INFO] Successfully to stopped Octoprint for '{profile_name}'")
    ctx.exit(0)


@main.command()
@click.pass_context
@click.argument('profile_name')
def restart(ctx, profile_name):
    """
    This stop Octoprint for a specific printer profile
    """
    ctx.obj['profile_name'] = profile_name
    ctx.obj['profile'] = get_profile(ctx)
    ctx.obj['pid_file'] = get_pid_filename(ctx, profile_name)

    if check_pidfile(ctx.obj['pid_file']):
        os.system(render_cmd(ctx, 'stop'))
        if not wait_command_timeout(ctx.obj['stop_timeout'], ctx.obj['pid_file'], False):
            click.echo(f"[ERROR] Failed to stop Octoprint for '{profile_name}'")
            ctx.exit(1)
    click.echo(f"[INFO] Successfully to stopped Octoprint for '{profile_name}'")

    os.system(render_cmd(ctx, 'start'))
    sleep(2)
    if wait_command_timeout(ctx.obj['start_timeout'], ctx.obj['pid_file'], True):
        click.echo(f"[INFO] Successfully to start Octoprint for '{profile_name}'")
        ctx.exit(0)
    click.echo(f"[ERROR] Failed to start Octoprint for '{profile_name}'")
    ctx.exit(1)


@main.command()
@click.pass_context
@click.argument('profile_name')
def status(ctx, profile_name):
    """
    This stop Octoprint for a specific printer profile
    """
    ctx.obj['profile_name'] = profile_name
    ctx.obj['profile'] = get_profile(ctx)
    ctx.obj['pid_file'] = get_pid_filename(ctx, profile_name)

    if check_pidfile(ctx.obj['pid_file']):
        click.echo(f"[INFO] Octoprint for '{profile_name}' is running")
    else:
        click.echo(f"[INFO] Octoprint for '{profile_name}' is stopped")
    ctx.exit(0)

if __name__ == "__main__":
    main()
