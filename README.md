This small python package has been made to enable the conversion from HPTLC image to csv files, with the aim of creating standardize databases.

The tool was developped Python 3.8. It requires python to be install on your machine.
Form the terminal, you can install the required packages by moving to the location of the hptlc package and running the following command:

```sh
pip install -r requirements.txt
```

Then, you can fill the config.py file with the information from your experiment and save the changes. This is the only file that you should need to modify. Once everything is setup you can run the tool.


On your terminal you can execute:
```sh
python -c 'import hptlc; hptlc.main()'
```

This will result in the creation of well structured, standardized, storage folders. However, it requires standard HPTLC procedures and does not allow anything else. 


If you want a simple conversion, even outside of the standard procedure, you can simply run:
```sh
python -c 'import hptlc; hptlc.single()'
```

In that case it will drop all the results in a single folder.


Finally, if you want to visualize some csv files you can run:
```sh
python -c 'import hptlc; hptlc.show_curve()'
```

It will show all the HPTLC curves specified in the variable "show" from the config file.
