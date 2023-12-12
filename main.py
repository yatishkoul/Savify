import argparse
import datetime
import os
import random
import string

import git
from git import Repo, Head
from git import exc
from tinydb import TinyDB, Query, where

pwd = os.getcwd()
app_path = os.path.join(pwd, ".savify")
remote = None

if not os.path.exists(app_path):
    os.mkdir(app_path)
db = TinyDB(os.path.join(app_path, "savify_db.json"))


def init_repo():
    r = Repo.init(pwd)
    print(f"Created new git repository at {pwd}")
    # This function just creates an empty file ...
    startup_test = os.path.join(app_path, "savify_init_object")
    with open(startup_test, "w") as f:
        f.write(f"Started using savify on {datetime.datetime.now()}")
        f.close()
    r.index.add([startup_test])
    r.index.commit("Started using savify!")
    infoexcludepath = os.path.join(
        pwd, os.path.join(".git", os.path.join("info", "exclude"))
    )
    with open(infoexcludepath, "a") as f:
        f.write(app_path)
        f.close()
    return r


try:
    repo = Repo(pwd)
except git.exc.NoSuchPathError as e:
    print("No existing git repository found")
    repo = init_repo()
except git.exc.InvalidGitRepositoryError as e:
    print("No valid git repository found")
    repo = init_repo()

master_branch = Head(repo, "refs/heads/master")


def get_file_versions(abs_filepath, do_print: False):
    commits_list = []
    file_tracking_head = get_file_tracking_head(abs_filepath)
    if file_tracking_head is None or len(file_tracking_head) == 0:
        return None
    for item in file_tracking_head:
        branch = item.get("branch")
        print("Stored versions of " + item.get("filename"))
        commits = list(repo.iter_commits(branch))
        commits_list.append(commits)
        if do_print:
            print_file_versions(commits)
    return commits_list


def print_file_versions(commits):
    for c in commits:
        creation_time = datetime.datetime.fromtimestamp(c.committed_date)
        print(
            f'🔖: "{c.hexsha}" 📄: "{c.message}" ⏱: "{creation_time}" 🙋: "{c.committer.name}"'
        )


def generate_commit_message(num_existing_versions):
    return "Version " + str(num_existing_versions + 1)


def track_new_file(abs_filepath):
    # Generate a new random branch name that is not already taken
    branch_already_exists = True
    while branch_already_exists:
        branch_name = "".join(
            random.SystemRandom().choice(string.ascii_letters + string.digits)
            for _ in range(20)
        )
        db_entry = Query()
        db_search = db.search(db_entry.branch == branch_name)
        branch_already_exists = len(db_search) > 0
    # Change the head reference to the new branch
    repo.head.reference = Head(repo, "refs/heads/" + branch_name)
    filename = os.path.basename(abs_filepath)
    db.insert({"filename": abs_filepath, "branch": branch_name})
    print(f"Created a new git branch called {branch_name} to track {filename}")
    repo.index.add([abs_filepath])
    repo.index.commit(generate_commit_message(0))
    repo.head.reference = master_branch
    print("Committed first version")


def commit_new_version(abs_filepath):
    tracking_head = get_file_tracking_head(abs_filepath)
    if tracking_head is None:
        print("ERROR: Cannot commit new versions of untracked files!")
        return None
    branch_name = tracking_head[0].get("branch")
    repo.head.reference = Head(repo, "refs/heads/" + branch_name)
    repo.index.add([os.path.join(pwd, abs_filepath)])
    commits = list(repo.iter_commits(branch_name))
    repo.index.commit(generate_commit_message(len(commits)))
    repo.head.reference = master_branch
    # in case file disappears -> print(f'git merge {branch_name} --allow-unrelated-histories --squash')
    abs_filepath = os.path.basename(abs_filepath)
    print(f"Stored new version of {abs_filepath}")


def get_file_tracking_head(abs_filepath):
    db_entry = Query()
    db_search = db.search(db_entry.filename == abs_filepath)
    if len(db_search) == 0:
        print(
            f"No versions of {os.path.basename(abs_filepath)} are currently being tracked by savify."
        )
        return None
    return db_search


def list_all_tracked_files():
    print("Files being tracked by savify:")
    all_entries = db.all()
    for item in all_entries:
        print(item.get("filename"))


def restore_file_to_version(filename, commit):
    repo.git.checkout(commit.hexsha, filename)
    print(f"{filename} successfully restored to version {hexsha}")


def delete_all_versions(abs_filepath, file_tracking_head):
    for item in file_tracking_head:
        try:
            repo.git.branch("-D", item.get("branch"))
        except git.exc.GitCommandError as e:
            pass
    db.remove(where("filename") == abs_filepath)
    print(f"Deleted all tracked versions of {os.path.basename(abs_filepath)}")


# TODO
def delete_file_version(abs_filepath, commit):
    pass

def set_remote(remote_name, url):
    global remote
    remote = repo.create_remote(remote_name, url)


def push_to_remote():
    global remote
    files = db.all()
    branches = {row['branch'] for row in files}     # set comprehension

    for branch in branches:
        branch_name = repo.get("branch")
        print('Pushing {}'.format(branch_name))
        remote.push(refspec='refs/heads/{}:refs/heads/{}'.format(branch_name, branch_name))
    #remote.push(refspec='{}:{}'.format(local_branch, remote_branch))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="versions",
        description="Track the various versions of your files using a simple CLI",
    )
    parser.add_argument(
        "cmd", help="The command that you want to run", type=str, nargs="*"
    )
    parser.add_argument(
        "-f",
        "--file",
        help="The file you want to run the command on",
        dest="filename",
        type=str,
    )
    parser.add_argument(
        "-t",
        "--tag",
        help="The tag value of a particular version of the file",
        dest="hexsha",
        type=str,
    )
    parser.add_argument(
        "--name",
        help="The name of the remote",
        dest="rem_name",
        type=str,
    )
    parser.add_argument(
        "--url",
        help="The url of the remote",
        dest="rem_url",
        type=str,
    )
    args = parser.parse_args()

    if len(args.cmd) == 0:
        parser.parse_args(["--help"])
    cmd = args.cmd[0]
    rel_filepath = args.filename
    # TODO run commands for multiple files
    if rel_filepath is None and len(args.cmd) > 1:
        all_rel_filepaths = args.cmd[1::]
        rel_filepath = all_rel_filepaths[0]

    if rel_filepath is not None and rel_filepath != " ":
        abs_filepath = os.path.abspath(rel_filepath)
        filename = os.path.basename(rel_filepath)

    if (cmd == "ls" or cmd == "list") and any(
        [rel_filepath == "", rel_filepath is None]
    ):
        if list_all_tracked_files() is None:
            exit(1)
        else:
            exit(0)

    if cmd == "remote":
        set_remote(args.rem_name, args.rem_url)
        exit(0)

    if cmd == "push":
        push_to_remote()
        exit(0)

    if rel_filepath is None:
        print(
            'No file specified. Use the --file flag to input a file. Run "savify --help" for more info.'
        )
        exit()

    file_exists = os.path.exists(abs_filepath)
    if not file_exists:
        print(f"{abs_filepath} does not exist")
        exit(1)

    if cmd == "rs" or cmd == "restore":
        file_tracking_head = get_file_tracking_head(abs_filepath)
        if file_tracking_head is None:
            print("ERROR: Cannot restore. File is not being tracked by versions.")
            exit(1)
        version_head = None
        hexsha = args.hexsha
        if hexsha is None:
            print(
                f"Tag value is required for savify to restore your file.\n"
                f'Run "savify ls --file {abs_filepath}" to find a list of all the stored versions of your file.'
            )
            exit(1)
        # Look for commits for the file with the user provided hexsha value
        for item in file_tracking_head:
            branch = item.get("branch")
            commits = list(repo.iter_commits(branch))
            version_head = list(filter(lambda c: c.hexsha == hexsha, commits))
        if version_head is None or len(version_head) == 0:
            print(f"No version of {rel_filepath} found for the tag {hexsha}")
            exit(1)
        restore_file_to_version(rel_filepath, version_head[0])

    # ls command for a particular file
    if cmd == "ls" or cmd == "list":
        versions = get_file_versions(abs_filepath, True)
        if versions is None or len(versions) == 0:
            exit(1)
        else:
            exit(0)

    if cmd == "commit" or cmd == "cm":
        file_tracking_head = get_file_tracking_head(abs_filepath)
        if file_tracking_head is None:
            track_new_file(abs_filepath)
        else:
            commit_new_version(abs_filepath)

    if cmd == "remove" or cmd == "rm":
        file_tracking_head = get_file_tracking_head(abs_filepath)
        if file_tracking_head is None:
            exit(0)
        version_head = None
        hexsha = args.hexsha
        if hexsha is None:
            print(
                f"Tag value is required for versions to know which version to delete.\n"
                f'Run "savify ls --file {abs_filepath}" to find a list of all the stored versions of your file.\n'
                'Use special tag value "all" to delete all versions of the file.'
            )
            exit(1)
        if hexsha == "all":
            delete_all_versions(abs_filepath, file_tracking_head)
            exit(0)
        # Look for commits for the file with the user provided hexsha value
        for item in file_tracking_head:
            branch = item.get("branch")
            commits = list(repo.iter_commits(branch))
            version_head = list(filter(lambda c: c.hexsha == hexsha, commits))
        if version_head is None or len(version_head) == 0:
            print(f"ERROR: No version of {filename} found for the tag {hexsha}")
            exit(0)
        delete_file_version(abs_filepath, version_head[0])

